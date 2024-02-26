import os
import sys
import argparse
import shutil
import compileall
import regex
import pylcs
from ast_comparer import ast_compare
from code_formatter import cleanup, anonymize, tokenize

SPLITTER = '-' * 42

parser = argparse.ArgumentParser(description='Code Antiplagiarism Project')

parser.add_argument('files', nargs='+', help='Files or directories to compare (filenames)')
parser.add_argument('-e', '--exclude', nargs='+', default=[], type=argparse.FileType('r'),
                    help='Files with content to exclude from comparison (filename)')
check_mode = parser.add_mutually_exclusive_group(required=True)
check_mode.add_argument('-q', '--quick', action='store_true', help='Run quick check (without comparing ASTs)')
check_mode.add_argument('-d', '--detailed', action='store_true', help='Run detailed check (with comparing ASTs)')
check_mode.add_argument('--double-layer', type=int,
                        help='Run detailed check only if the result of quick check is >= given number (in %%)')
parser.add_argument('-o', '--output', type=argparse.FileType('w'), default=sys.stdout, help='File to output logs')

args = parser.parse_args()

os.makedirs('temp', exist_ok=True)
with open('temp/exclude.txt', 'w') as exclude:
    for file in args.exclude:
        text = file.read()
        text = regex.sub(r' {4}', '\t', text)
        text = regex.sub(r'#.*', '', text)
        exclude.write(f'{text}\n{SPLITTER}\n')


def edit_distance_ratio(object1, object2):
    return pylcs.edit_distance(object1, object2) / max(len(object1), len(object2))


def lcs_ratio(object1, object2):
    return pylcs.lcs(object1, object2) / max(len(object1), len(object2))


def check_similarity(source_filename, modified_filename):
    with open(source_filename) as source_file:
        source = source_file.read()
    with open(modified_filename) as modified_file:
        modified = modified_file.read()
    path_p = regex.compile(r'[\/\\]')
    source_filename = regex.sub(path_p, '', source_filename)
    modified_filename = regex.sub(path_p, '', modified_filename)

    source_normalized = cleanup(source)
    modified_normalized = cleanup(modified)

    with open('normalized.txt', 'w') as normalized:
        normalized.write(f'{SPLITTER} SOURCE {SPLITTER}\n')
        normalized.write(source_normalized)
        normalized.write(f'\n\n{SPLITTER} MODIFIED {SPLITTER}\n')
        normalized.write(modified_normalized)

    source_tokenized = tokenize(source_normalized)
    modified_tokenized = tokenize(modified_normalized)
    source_anonymized = anonymize(source_normalized)
    modified_anonymized = anonymize(modified_normalized)

    with open(f'temp/{source_filename}_anonymized.py', 'w') as code:
        code.write(source_anonymized)
    with open(f'temp/{modified_filename}_anonymized.py', 'w') as code:
        code.write(modified_anonymized)
    compileall.compile_file(f'temp/{source_filename}_anonymized.py', quiet=2, legacy=True)
    compileall.compile_file(f'temp/{modified_filename}_anonymized.py', quiet=2, legacy=True)
    with open(f'temp/{source_filename}_anonymized.pyc', 'rb') as bytecode:
        source_bytecode = bytecode.read()
    with open(f'temp/{modified_filename}_anonymized.pyc', 'rb') as bytecode:
        modified_bytecode = bytecode.read()

    normalized_distance = 1 - edit_distance_ratio(source_anonymized, modified_anonymized)
    tokenized_distance = lcs_ratio(source_tokenized, modified_tokenized)
    bytecode_distance = 1 - edit_distance_ratio(source_bytecode, modified_bytecode)
    ast_distance = -1

    if args.detailed:
        ast_distance = 1 - ast_compare(source_anonymized, modified_anonymized)
        stable_distance = normalized_distance + tokenized_distance + ast_distance
        final_result = (stable_distance + (1 if bytecode_distance > 0.75 else stable_distance / 3)) / 4
    elif args.quick:
        stable_distance = normalized_distance + tokenized_distance
        final_result = (stable_distance + (1 if bytecode_distance > 0.75 else stable_distance / 2)) / 3
    elif args.double_layer:
        stable_distance = normalized_distance + tokenized_distance
        middle_result = (stable_distance + (1 if bytecode_distance > 0.75 else stable_distance / 2)) / 3
        if middle_result * 100 >= args.double_layer:
            ast_distance = 1 - ast_compare(source_anonymized, modified_anonymized)
            stable_distance += ast_distance
            final_result = (stable_distance + (1 if bytecode_distance > 0.75 else stable_distance / 3)) / 4
        else:
            final_result = middle_result

    print(f'1) Normalized: {round(normalized_distance * 100)}% match', file=args.output)
    print(f'2) Tokenized: {round(tokenized_distance * 100)}% match', file=args.output)
    print(f'3) Bytecode: {round(bytecode_distance * 100)}% match', file=args.output)
    if ast_distance != -1:
        print(f'4) AST: {round(ast_distance * 100)}% match', file=args.output)
    print(f'Final Result: {round(final_result * 100)}% match', file=args.output)

    return round(final_result * 100)


directories = 0
for file in args.files:
    if os.path.isdir(file):
        directories += 1

suspicious = []
if directories == 0:
    if len(args.files) == 1:
        print(f'{sys.argv[0]}: error: argument files: nothing to compare with')
        sys.exit(1)
    else:
        processed = []
        for source_name in args.files:
            for modified_name in args.files:
                if source_name != modified_name and (source_name, modified_name) not in processed:
                    print(f'Checking the similarity of {source_name} and {modified_name}', file=args.output)
                    result = check_similarity(source_name, modified_name)
                    if result >= 75:
                        suspicious.append((source_name, modified_name, result))
                    print(SPLITTER, file=args.output)
                    processed.append((source_name, modified_name))
                    processed.append((modified_name, source_name))
elif directories == 1:
    if len(args.files) == 1:
        files = [file for file in os.listdir(args.files[0])
                 if os.path.isfile(os.path.join(args.files[0], file)) and file[-3:] == '.py']
        processed = []
        for source_name in files:
            for modified_name in files:
                if source_name != modified_name and (source_name, modified_name) not in processed:
                    print(f'Checking the similarity of {source_name} and {modified_name}', file=args.output)
                    result = check_similarity(os.path.join(args.files[0], source_name),
                                              os.path.join(args.files[0], modified_name))
                    if result >= 75:
                        suspicious.append((source_name, modified_name, result))
                    print(SPLITTER, file=args.output)
                    processed.append((source_name, modified_name))
                    processed.append((modified_name, source_name))
    else:
        print(f'{sys.argv[0]}: error: argument files: cannot compare files with directories')
        sys.exit(1)
else:
    print(f'{sys.argv[0]}: error: argument files: only one directory is supported')
    sys.exit(1)

if len(args.files) > 2 or directories == 1:
    suspicious.sort(key=lambda e: e[2], reverse=True)
    print('Top Suspicious: above 75% of similarity\n\n', file=args.output)
    for source_name, modified_name, result in suspicious:
        print(f'{source_name} and {modified_name}: {result}% match', file=args.output)

shutil.rmtree('temp')
