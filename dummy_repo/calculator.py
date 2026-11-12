# dummy_repo/calculator.py

def add(a, b):
    return a + b

# keep the comments as it is

def subtract(a, b):
    return a - b

# New multiply function added

def multiply(a, b, c=None):
    """Return the product of two or three numbers.
    If a third argument is provided, multiply all three.
    """
    if c is not None:
        return a * b * c
    return a * b

# New divide function added

def divide(a, b):
    """Return the result of dividing a by b.
    If b is zero, returns the string "Error: Division by zero".
    """
    if b == 0:
        return "Error: Division by zero"
    return a / b

# New modulo function added

def modulo(a, b):
    """Return the remainder of a divided by b.
    If b is zero, returns the string "Error: Division by zero".
    """
    if b == 0:
        return "Error: Division by zero"
    return a % b

# New power function added

def power(a, b):
    """Return a raised to the power of b.
    
    Parameters:
        a (numeric): The base value.
        b (numeric): The exponent value.
    
    Returns:
        numeric: The result of a ** b.
    """
    return a ** b

if __name__ == "__main__":
    print("10 + 5 =", add(10, 5))
    print("10 * 5 =", multiply(10, 5))
    print("10 * 5 * 2 =", multiply(10, 5, 2))
    print("10 / 2 =", divide(10, 2))
    print("10 / 0 =", divide(10, 0))
    print("10 % 3 =", modulo(10, 3))
    print("2 ** 3 =", power(2, 3))