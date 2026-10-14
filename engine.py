import re
from decimal import Decimal, DecimalException, DivisionByZero, InvalidOperation, localcontext, ROUND_HALF_UP


class CalculationError(ValueError):
    pass


class IncompleteExpression(CalculationError):
    pass


TOKEN = re.compile(r'\d+(?:\.\d*)?|\.\d+|[()+*/-]')
NUMBER_AT_END = re.compile(r'(?:\d+(?:\.\d*)?|\.\d+)$')


def decimal_string(value):
    if not value.is_finite():
        raise CalculationError('Result is too large')
    if value == 0:
        return '0'
    text = format(value, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def display_number(text, places=6):
    try:
        value = Decimal(text)
        if not value.is_finite():
            return 'Invalid result'
        with localcontext() as ctx:
            ctx.prec = max(80, len(value.as_tuple().digits) + max(0, value.adjusted()) + places + 16)
            rounded = value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
            return decimal_string(rounded)
    except (DecimalException, ValueError, TypeError):
        return 'Invalid result'


def calculate(expression):
    expression = ''.join(expression.split())
    if not expression:
        raise IncompleteExpression('Enter a calculation')
    if len(expression) > 512:
        raise CalculationError('Expression limit reached')
    tokens = []
    offset = 0
    while offset < len(expression):
        match = TOKEN.match(expression, offset)
        if not match:
            if expression[offset:] == '.':
                raise IncompleteExpression('Finish your number')
            raise CalculationError('Invalid expression')
        tokens.append(match.group())
        offset = match.end()
    values, operators = [], []
    precedence = {'+': 1, '-': 1, '*': 2, '/': 2, 'u+': 3, 'u-': 3}

    def apply():
        operator = operators.pop()
        if operator in ('u+', 'u-'):
            if not values:
                raise IncompleteExpression('Finish your expression')
            value = values.pop()
            values.append(-value if operator == 'u-' else value)
            return
        if len(values) < 2:
            raise IncompleteExpression('Finish your expression')
        right, left = values.pop(), values.pop()
        if operator == '+':
            values.append(left + right)
        elif operator == '-':
            values.append(left - right)
        elif operator == '*':
            values.append(left * right)
        elif operator == '/':
            if right == 0:
                raise CalculationError('Cannot divide by zero')
            values.append(left / right)

    try:
        with localcontext() as ctx:
            ctx.prec = max(80, len(expression) * 2 + 32)
            expecting_number = True
            for token in tokens:
                if token[0].isdigit() or token[0] == '.':
                    if not expecting_number:
                        raise CalculationError('Missing operator')
                    values.append(Decimal(token))
                    expecting_number = False
                elif token == '(':
                    if not expecting_number:
                        raise CalculationError('Missing operator')
                    operators.append(token)
                elif token == ')':
                    if expecting_number:
                        raise CalculationError('Invalid parentheses')
                    while operators and operators[-1] != '(':
                        apply()
                    if not operators:
                        raise CalculationError('Invalid parentheses')
                    operators.pop()
                    expecting_number = False
                else:
                    if expecting_number:
                        if token not in ('+', '-'):
                            raise IncompleteExpression('Finish your expression')
                        operators.append('u' + token)
                    else:
                        while operators and operators[-1] != '(' and precedence[operators[-1]] >= precedence[token]:
                            apply()
                        operators.append(token)
                        expecting_number = True
            if expecting_number or '(' in operators:
                raise IncompleteExpression('Finish your expression')
            while operators:
                apply()
            if len(values) != 1:
                raise CalculationError('Invalid expression')
            return decimal_string(values[0])
    except DivisionByZero:
        raise CalculationError('Cannot divide by zero')
    except (InvalidOperation, DecimalException, OverflowError):
        raise CalculationError('Result is too large')


def pretty(expression):
    return expression.replace('*', ' × ').replace('/', ' ÷ ').replace('+', ' + ').replace('-', '−')
