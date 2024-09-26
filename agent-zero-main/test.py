import sys

print("Hello, World!")
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")

# Test f-string
name = "Python"
print(f"Hello, {name}!")


# Test basic function definition and call
def greet(name):
    return f"Hello, {name}!"


print(greet("User"))

if __name__ == "__main__":
    print("This is a test script.")
