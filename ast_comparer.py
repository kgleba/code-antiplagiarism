import ast
import zss

TREE_SIZE = []


def build(node: ast.AST | list | str) -> zss.Node:
    if isinstance(node, ast.Module):
        TREE_SIZE.append(0)

    TREE_SIZE[-1] += 1

    if isinstance(node, ast.AST):
        node_type = type(node).__name__
        fields = []
        for field, attr in ast.iter_fields(node):
            if isinstance(attr, list):
                fields += [build(child) for child in attr]
            else:
                fields.append(zss.Node(field, [build(attr)]))

        return zss.Node(node_type, fields)

    return zss.Node(node, [])


def ast_compare(source: str, modified: str) -> float:
    source_ast = ast.parse(source)
    modified_ast = ast.parse(modified)

    source_zss = build(source_ast)
    modified_zss = build(modified_ast)

    ratio = zss.simple_distance(source_zss, modified_zss) / max(TREE_SIZE)
    return ratio / 2
