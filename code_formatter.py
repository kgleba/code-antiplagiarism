import dis
import regex

SPLITTER = '-' * 42
KEYWORDS = ['False', 'None', 'True', '__import__', 'abs', 'add', 'all', 'and', 'any', 'append', 'as', 'ascii', 'assert', 'async', 'await',
            'bin', 'bool', 'break', 'bytearray', 'bytes', 'callable', 'capitalize', 'chr', 'class', 'classmethod', 'clear', 'compile',
            'complex', 'continue', 'copy', 'count', 'def', 'del', 'delattr', 'dict', 'difference', 'dir', 'discard', 'divmod', 'elif',
            'else', 'enumerate', 'eval', 'except', 'exec', 'filter', 'finally', 'find', 'float', 'flush', 'for', 'format', 'from',
            'fromkeys', 'frozenset', 'get', 'getattr', 'global', 'globals', 'hasattr', 'hash', 'help', 'hex', 'if', 'import', 'in', 'index',
            'input', 'insert', 'int', 'intersection', 'is', 'isalnum', 'isinstance', 'issubclass', 'issubset', 'items', 'iter', 'keys',
            'lambda', 'len', 'list', 'locals', 'map', 'max', 'memoryview', 'min', 'next', 'nonlocal', 'not', 'object', 'oct', 'open', 'or',
            'ord', 'os.chdir', 'os.environ', 'os.getcwd', 'os.getenv', 'os.listdir', 'os.mkdir', 'os.putenv', 'os.remove', 'os.rename',
            'os.rmdir', 'os.system', 'pass', 'pop', 'pow', 'print', 'raise', 'range', 'read', 'readline', 'readlines', 'remove', 'repr',
            'return', 'reverse', 'reversed', 'round', 'seek', 'set', 'setattr', 'slice', 'sort', 'sorted', 'staticmethod', 'str', 'sum',
            'super', 'symmetric_difference', 'sys.argv', 'sys.exit', 'sys.module', 'sys.path', 'sys.platform', 'sys.setrecursionlimit',
            'sys.stderr', 'sys.stdin', 'sys.stdout', 'try', 'tuple', 'type', 'union', 'values', 'vars', 'while', 'with', 'write',
            'writeline', 'yield', 'zip']


def traverse_bytecode_instructions(code) -> list[dis.Instruction]:
    all_instructions = []
    module_level = dis.get_instructions(code)
    for instruction in module_level:
        if type(instruction.argval).__name__ == 'code':
            all_instructions += traverse_bytecode_instructions(instruction.argval)
        else:
            all_instructions.append(instruction)

    return all_instructions


def cleanup(code: str) -> str:
    code = regex.sub(r' {4}', '\t', code)  # 4 whitespaces - to tab
    code = regex.sub(r'#.*', '', code)
    code = regex.sub(r'\'\'\'[^\']*\'\'\'', '', code)
    code = regex.sub(r'"""[^"]*"""', '', code)  # remove comments

    # format arithmetical (and other whitespace-independent) expressions
    edited_word = '[a-zA-Z0-9_\[\]]'
    operator = '(\*|\/|-|\+|%|=|<|>|\||\&|\^)'
    ws_ind_p = regex.compile(fr'({edited_word}+) *({operator}+) *({edited_word}+) *((({operator}+) *({edited_word}+) *)*)')
    for match in regex.finditer(ws_ind_p, code):
        formatted = f'{match.group(1)} {match.group(2)} {match.group(4)}'
        alt_operators = match.captures(7)
        alt_operands = match.captures(9)

        for i in range(len(alt_operands)):
            if alt_operators[i] and alt_operands[i]:
                formatted += f' {alt_operators[i]} {alt_operands[i]}'

        if match.group(0)[-1] == ' ':
            formatted += ' '

        code = code.replace(match.group(0), formatted)

    # remove specified "exclude" patterns
    exclude = open('temp/exclude.txt').read().split(f'\n{SPLITTER}\n')
    for pattern in exclude:
        code = code.replace(pattern, '')

    # remove unused imports
    imports = [instruction.argval for instruction in traverse_bytecode_instructions(code) if instruction.opname == 'IMPORT_NAME']

    for lib in imports:
        if code.count(lib) == 1:
            code = code.replace(f'import {lib}', '')
            code = regex.sub(fr'from {lib} import .+', '', code)
            code = regex.sub(fr'(import \w+,*) *((\w+,)*) *{lib},* *(\w*)', r'\1 \2 \4', code)

    code = regex.sub(r' +', ' ', code)  # multiple whitespaces - to single
    code = regex.sub(r'\n{2,}', '\n', code)  # multiple line feeds - to single

    code = code.strip()
    code = '\n'.join(map(lambda s: s.rstrip(), code.split('\n')))
    code = '\n'.join(
        map(lambda s: s[:-1] if s and s[-1] == ',' and (regex.match(r'import', s) or regex.match(r'from', s)) else s, code.split('\n')))

    # remove unused variables
    store_variables = [instruction.argval for instruction in traverse_bytecode_instructions(code)
                       if instruction.opname in ('STORE_FAST', 'STORE_DEREF', 'STORE_GLOBAL', 'STORE_NAME')]
    load_variables = [instruction.argval for instruction in traverse_bytecode_instructions(code)
                      if instruction.opname in ('LOAD_FAST', 'LOAD_DEREF', 'LOAD_GLOBAL', 'LOAD_NAME', 'LOAD_CLASSDEREF')]
    unused_variables = set(store_variables) - set(load_variables)

    for variable in unused_variables:
        code = regex.sub(fr'{variable} = .+', '', code)
    code = regex.sub(r'\n{2,}', '\n', code)

    code = code.strip()
    code = '\n'.join(map(lambda s: s.rstrip(), code.split('\n')))  # remove trailing whitespaces etc. at the end of every string

    return code


def anonymize(code: str) -> str:
    variables = [instruction.argval for instruction in traverse_bytecode_instructions(code)
                 if instruction.opname in ('STORE_FAST', 'STORE_DEREF', 'STORE_GLOBAL', 'STORE_NAME')]

    cnt = 0

    for variable in variables:
        code = regex.sub(fr'(\(|\)|\.| |=|\[|\]|\,|\t|^){variable}(\(|\)|\.| |=|\[|\]|\,|:|\t|$)', fr'\1var_{cnt}\2', code,
                         flags=regex.MULTILINE)
        cnt += 1

    return code


def tokenize(code: str) -> str:
    variables = set([instruction.argval for instruction in traverse_bytecode_instructions(code)
                     if instruction.opname in ('STORE_FAST', 'STORE_DEREF', 'STORE_GLOBAL', 'STORE_NAME',
                                               'LOAD_FAST', 'LOAD_DEREF', 'LOAD_GLOBAL', 'LOAD_NAME', 'LOAD_CLASSDEREF')])

    for keyword in KEYWORDS:
        code = regex.sub(fr'(\(|\)|\.| |=|\[|\]|\,|\t|^){keyword}(\(|\)|\.| |=|\[|\]|\,|:|\t|$)', fr'\1k\2', code,
                         flags=regex.MULTILINE)
    for variable in variables:
        code = regex.sub(fr'(\(|\)|\.| |=|\[|\]|\,|\t|^){variable}(\(|\)|\.| |=|\[|\]|\,|:|\t|$)', fr'\1i\2', code,
                         flags=regex.MULTILINE)
    code = regex.sub(r'-*\d+', 'n', code)

    code = regex.sub(r'(.*i(\([^)]*\))?\.)([a-zA-Z0-9_\[\]]*)', r'\1i', code)

    return code
