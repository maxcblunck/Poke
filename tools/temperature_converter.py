def celsius_to_fahrenheit(c):
    return c * 9 / 5 + 32

def fahrenheit_to_celsius(f):
    return (f - 32) * 5 / 9

def celsius_to_kelvin(c):
    return c + 273.15

def run():
    print("Temperature Converter")
    print("Scales: C (Celsius), F (Fahrenheit), K (Kelvin)")

    try:
        value = float(input("Enter temperature value: "))
        from_scale = input("From scale (C/F/K): ").upper()
        to_scale = input("To scale   (C/F/K): ").upper()
    except ValueError:
        print("Invalid input.")
        return

    if from_scale == to_scale:
        print(f"Result: {value}")
        return

    conversions = {
        ("C", "F"): celsius_to_fahrenheit,
        ("F", "C"): fahrenheit_to_celsius,
        ("C", "K"): celsius_to_kelvin,
        ("K", "C"): lambda k: k - 273.15,
        ("F", "K"): lambda f: celsius_to_kelvin(fahrenheit_to_celsius(f)),
        ("K", "F"): lambda k: celsius_to_fahrenheit(k - 273.15),
    }

    fn = conversions.get((from_scale, to_scale))
    if fn is None:
        print("Unsupported conversion.")
        return

    result = fn(value)
    print(f"Result: {value}°{from_scale} = {result:.2f}°{to_scale}")

if __name__ == "__main__":
    run()
