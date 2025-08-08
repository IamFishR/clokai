# Enhanced system info script
import sys

def get_system_specs():
    print('System Specifications:')
    print('Python version:', sys.version)
    print('Platform:', sys.platform)

if __name__ == '__main__':
    get_system_specs()


def add_numbers(a, b):
    """Add two numbers and return the result"""
    return a + b

# Test the function
if __name__ == '__main__':
    print(f'5 + 3 = {add_numbers(5, 3)}')
print('Added a print statement!')
print('Hello from the new print statement!')
print('Final test print statement!')