import ast
import re
import operator
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import json
import keyword
from functools import lru_cache

class ExpressionError(Exception):
    """Expression evaluation error"""
    def __init__(self, message: str, expression: str = "", position: int = 0):
        super().__init__(message)
        self.expression = expression
        self.position = position
        self.context = {}

class SafeExpressionEvaluator:
    """Safe expression evaluator for n8n-style expressions"""
    
    def __init__(self):
        self.allowed_names = {
            # Math functions
            'abs', 'round', 'floor', 'ceil', 'min', 'max', 'sum',
            # String functions
            'len', 'str', 'int', 'float', 'bool',
            # Date functions
            'now', 'today',
            # Utility functions
            'range', 'enumerate', 'zip', 'list', 'dict', 'set',
            # N8n variables (mapped names)
            'n8n_json', 'n8n_binary', 'n8n_items', 'n8n_item', 'n8n_node', 
            'n8n_workflow', 'n8n_execution', 'n8n_now', 'n8n_today', 'n8n_parameter',
            # Node reference function
            'n8n_node_ref'
        }
        
        # ... rest of your operators, comparisons, unary_ops remain the same ...
        self.operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.LShift: operator.lshift,
            ast.RShift: operator.rshift,
            ast.BitOr: operator.or_,
            ast.BitXor: operator.xor,
            ast.BitAnd: operator.and_,
            ast.MatMult: operator.matmul,
        }
        
        self.comparisons = {
            ast.Eq: operator.eq,
            ast.NotEq: operator.ne,
            ast.Lt: operator.lt,
            ast.LtE: operator.le,
            ast.Gt: operator.gt,
            ast.GtE: operator.ge,
            ast.Is: operator.is_,
            ast.IsNot: operator.is_not,
            ast.In: lambda x, y: x in y,
            ast.NotIn: lambda x, y: x not in y,
        }
        
        self.unary_ops = {
            ast.UAdd: operator.pos,
            ast.USub: operator.neg,
            ast.Not: operator.not_,
            ast.Invert: operator.invert,
        }

    def evaluate(self, expression: str, context: Dict[str, Any]) -> Any:
        """Evaluate an expression safely"""
        try:
            # Preprocess the expression to handle n8n variables
            processed_expression, processed_context = self._preprocess_n8n_expression(expression, context)
            
            # Parse the expression into an AST
            tree = ast.parse(processed_expression, mode='eval')
            return self._eval_node(tree.body, processed_context)
        except SyntaxError as e:
            raise ExpressionError(f"Syntax error in expression: {str(e)}", expression)
        except Exception as e:
            raise ExpressionError(f"Expression evaluation failed: {str(e)}", expression)

    def _preprocess_n8n_expression(self, expression: str, context: Dict[str, Any]) -> tuple:
        """
        Preprocess n8n-style expressions to make them Python-compatible
        
        Returns:
            tuple: (processed_expression, processed_context)
        """
        # Handle JavaScript-style ternary operators: condition ? true_val : false_val
        # Convert to Python: true_val if condition else false_val
        # This regex matches: <condition> ? <true_value> : <false_value>
        ternary_pattern = r'([^?]+)\s*\?\s*([^:]+)\s*:\s*(.+)'
        ternary_match = re.match(ternary_pattern, expression.strip())
        if ternary_match:
            condition = ternary_match.group(1).strip()
            true_val = ternary_match.group(2).strip()
            false_val = ternary_match.group(3).strip()
            expression = f"({true_val}) if ({condition}) else ({false_val})"
        
        # Handle node reference syntax: $('NodeName') -> n8n_node_ref('NodeName')
        node_ref_pattern = r"\$\('([^']+)'\)"
        expression = re.sub(node_ref_pattern, r"n8n_node_ref('\1')", expression)
        
        # Handle other node reference formats: $("NodeName") -> n8n_node_ref("NodeName")
        node_ref_pattern2 = r'\$\("([^"]+)"\)'
        expression = re.sub(node_ref_pattern2, r'n8n_node_ref("\1")', expression)
        
        # Create mapping for n8n variables to Python-safe names
        n8n_mappings = {
            '$json': 'n8n_json',
            '$binary': 'n8n_binary', 
            '$items': 'n8n_items',
            '$item': 'n8n_item',
            '$node': 'n8n_node',
            '$workflow': 'n8n_workflow',
            '$execution': 'n8n_execution',
            '$now': 'n8n_now',
            '$today': 'n8n_today',
            '$parameter': 'n8n_parameter'
        }
        
        processed_expression = expression
        processed_context = {}
        
        # Replace n8n variables with Python-safe names
        for n8n_var, safe_var in n8n_mappings.items():
            if n8n_var in processed_expression:
                # Use word boundary to avoid partial replacements
                pattern = r'\$' + re.escape(n8n_var[1:]) + r'\b'
                processed_expression = re.sub(pattern, safe_var, processed_expression)
            
            # Add to processed context if exists in original context
            if n8n_var in context:
                processed_context[safe_var] = context[n8n_var]
        
        # Add node reference function to context
        processed_context['n8n_node_ref'] = context.get('$node_ref', lambda x: {})

        # Rewrite attribute access to reserved words (e.g. .from -> ['from'])
        @lru_cache(maxsize=1)
        def _reserved() -> set[str]:
            return set(keyword.kwlist)
        
        def _fix_reserved_attr(m: re.Match) -> str:
            name = m.group(1)
            return f"['{name}']" if name in _reserved() else f".{name}"
        
        processed_expression = re.sub(r"\.([A-Za-z_][A-Za-z0-9_]*)", _fix_reserved_attr, processed_expression)
        
        # Add all other context items
        for key, value in context.items():
            if not key.startswith('$'):
                processed_context[key] = value
        
        return processed_expression, processed_context

    # ... rest of your _eval_node method remains exactly the same ...
    def _eval_node(self, node: ast.AST, context: Dict[str, Any]) -> Any:
        """Recursively evaluate AST nodes"""
        
        if isinstance(node, ast.Constant):
            return node.value
        
        elif isinstance(node, ast.Name):
            if node.id in context:
                return context[node.id]
            elif node.id in self.allowed_names:
                return self._get_builtin_function(node.id)
            else:
                raise NameError(f"Name '{node.id}' is not defined")
        
        elif isinstance(node, ast.Attribute):
            # FIXED: Evaluate the object (node.value), not the attribute name
            obj = self._eval_node(node.value, context)
            
            # Handle special cases for safe attribute access
            if obj is None:
                return None
            
            # For dictionaries, treat attribute access as key access
            if isinstance(obj, dict) and node.attr in obj:
                return obj[node.attr]
            
            # Standard attribute access
            if hasattr(obj, node.attr):
                return getattr(obj, node.attr)
            
            # If attribute doesn't exist, return None (like n8n behavior)
            return None
        
        elif isinstance(node, ast.Subscript):
            obj = self._eval_node(node.value, context)
            key = self._eval_node(node.slice, context)
            
            # Handle None safely
            if obj is None:
                return None
            
            # Safe key access for dictionaries
            if isinstance(obj, dict):
                return obj.get(key)
            
            # Safe index access for lists
            if isinstance(obj, list) and isinstance(key, int):
                return obj[key] if 0 <= key < len(obj) else None
            
            return obj[key]
        
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left, context)
            right = self._eval_node(node.right, context)
            op = self.operators.get(type(node.op))
            if op:
                return op(left, right)
            else:
                raise ValueError(f"Unsupported binary operator: {type(node.op)}")
        
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand, context)
            op = self.unary_ops.get(type(node.op))
            if op:
                return op(operand)
            else:
                raise ValueError(f"Unsupported unary operator: {type(node.op)}")
        
        elif isinstance(node, ast.Compare):
            left = self._eval_node(node.left, context)
            for op, right_node in zip(node.ops, node.comparators):
                right = self._eval_node(right_node, context)
                comparison = self.comparisons.get(type(op))
                if comparison:
                    if not comparison(left, right):
                        return False
                    left = right
                else:
                    raise ValueError(f"Unsupported comparison: {type(op)}")
            return True
        
        elif isinstance(node, ast.IfExp):
            # Handle Python ternary: value_if_true if condition else value_if_false
            test = self._eval_node(node.test, context)
            if test:
                return self._eval_node(node.body, context)
            else:
                return self._eval_node(node.orelse, context)
        
        elif isinstance(node, ast.Call):
            return self._eval_call(node, context)
        
        elif isinstance(node, ast.List):
            return [self._eval_node(item, context) for item in node.elts]
        
        elif isinstance(node, ast.Dict):
            return {
                self._eval_node(k, context): self._eval_node(v, context)
                for k, v in zip(node.keys, node.values)
            }
        
        elif isinstance(node, ast.Slice):
            return slice(
                self._eval_node(node.lower, context) if node.lower else None,
                self._eval_node(node.upper, context) if node.upper else None,
                self._eval_node(node.step, context) if node.step else None
            )
        
        else:
            raise ValueError(f"Unsupported node type: {type(node)}")

    def _eval_call(self, node: ast.Call, context: Dict[str, Any]) -> Any:
        """Evaluate function calls"""
        func = self._eval_node(node.func, context)
        args = [self._eval_node(arg, context) for arg in node.args]
        kwargs = {
            kw.arg: self._eval_node(kw.value, context) 
            for kw in node.keywords
        }
        
        # Security check for callable
        if not callable(func):
            raise ValueError(f"Object is not callable: {func}")
        
        return func(*args, **kwargs)

    def _get_builtin_function(self, name: str) -> Callable:
        """Get safe builtin functions"""
        builtins = {
            'abs': abs,
            'round': round,
            'floor': lambda x: int(x),
            'ceil': lambda x: int(x) + (1 if x % 1 else 0),
            'min': min,
            'max': max,
            'sum': sum,
            'len': len,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'now': datetime.now,
            'today': lambda: datetime.now().date(),
            'range': range,
            'enumerate': enumerate,
            'zip': zip,
            'list': list,
            'dict': dict,
            'set': set,
        }
        return builtins.get(name)

# ExpressionEngine class remains the same
class ExpressionEngine:
    """N8n-style expression engine"""
    
    def __init__(self):
        self.evaluator = SafeExpressionEvaluator()
        self.expression_pattern = re.compile(r'\{\{(.*?)\}\}', re.DOTALL)
    
    def evaluate_parameter(
        self, 
        value: Any, 
        context: Dict[str, Any],
        item_index: int = 0
    ) -> Any:
        """Evaluate expressions in a parameter value"""
        
        if not isinstance(value, str):
            return value
        
        # Check if it contains expressions
        matches = list(self.expression_pattern.finditer(value))
        if not matches:
            return value
        
        # If the entire string is one expression, return the evaluated result
        if len(matches) == 1 and matches[0].span() == (0, len(value)):
            expression = matches[0].group(1).strip()
            return self._evaluate_expression(expression, context, item_index)
        
        # Replace expressions in string
        result = value
        for match in reversed(matches):  # Reverse to maintain positions
            expression = match.group(1).strip()
            evaluated = self._evaluate_expression(expression, context, item_index)
            result = result[:match.start()] + str(evaluated) + result[match.end():]
        
        return result
    
    def _evaluate_expression(self, expression: str, context: Dict[str, Any], item_index: int) -> Any:
        """Evaluate a single expression"""
        
        # Build enhanced context with helper functions
        enhanced_context = {
            **context,
            **self._get_helper_functions(context, item_index)
        }
        
        try:
            return self.evaluator.evaluate(expression, enhanced_context)
        except Exception as e:
            raise ExpressionError(f"Failed to evaluate expression '{expression}': {str(e)}")
    
    def _get_helper_functions(self, context: Dict[str, Any], item_index: int) -> Dict[str, Any]:
        """Get helper functions for expressions"""
        
        def get_item(index: Optional[int] = None) -> Dict[str, Any]:
            """Get item by index"""
            idx = index if index is not None else item_index
            items = context.get('$items', [])
            if 0 <= idx < len(items):
                item = items[idx]
                if hasattr(item, 'json_data'):
                    return item.json_data
                return item
            return {}
        
        def get_items() -> List[Dict[str, Any]]:
            """Get all items"""
            items = context.get('$items', [])
            return [
                item.json_data if hasattr(item, 'json_data') else item 
                for item in items
            ]
        
        def date_format(date_val: Any, format_str: str = "%Y-%m-%d") -> str:
            """Format date"""
            if isinstance(date_val, str):
                date_val = date_parser.parse(date_val)
            elif isinstance(date_val, (int, float)):
                date_val = datetime.fromtimestamp(date_val)
            
            if isinstance(date_val, datetime):
                return date_val.strftime(format_str)
            return str(date_val)
        
        def json_parse(json_str: str) -> Any:
            """Parse JSON string"""
            return json.loads(json_str)
        
        def json_stringify(obj: Any) -> str:
            """Convert object to JSON string"""
            return json.dumps(obj)
        
        return {
            '$item': get_item,
            '$items': get_items,
            'dateFormat': date_format,
            'jsonParse': json_parse,
            'jsonStringify': json_stringify,
            'Math': {
                'floor': lambda x: int(x),
                'ceil': lambda x: int(x) + (1 if x % 1 else 0),
                'round': round,
                'abs': abs,
                'min': min,
                'max': max,
            },
            'String': {
                'toLowerCase': lambda s: str(s).lower(),
                'toUpperCase': lambda s: str(s).upper(),
                'trim': lambda s: str(s).strip(),
                'split': lambda s, sep: str(s).split(sep),
                'replace': lambda s, old, new: str(s).replace(old, new),
            }
        }