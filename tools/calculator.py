def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        return "Error: division by zero"
    return a / b

def run():
    print("Simple Calculator")
    print("-----------------")
    try:
        a = float(input("Enter first number: "))
        op = input("Operation (+, -, *, /): ")
        b = float(input("Enter second number: "))
    except ValueError:
        print("Invalid input.")
        return

    ops = {"+": add, "-": subtract, "*": multiply, "/": divide}
    if op not in ops:
        print("Unknown operation.")
        return

    result = ops[op](a, b)
    print(f"Result: {a} {op} {b} = {result}")

if __name__ == "__main__":
    run()
