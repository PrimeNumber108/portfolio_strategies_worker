import os

def show_env():
    for key, value in os.environ.items():
        print(f"{key} = {value}")

if __name__ == "__main__":
    show_env()
