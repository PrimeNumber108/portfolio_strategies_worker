import sys
def get_arg(index, default=''):
    return sys.argv[index] if len(sys.argv) > index else default

