import sys


def main():
    # TODO: Uncomment the code below to pass the first stage
    while True:
        sys.stdout.write("$ ")
        command = input()
        if command[0:4] == "echo":
            print(command[5:])
        elif command == "exit":
            break
        else:
            print(f"{command}: command not found")


if __name__ == "__main__":
    main()
