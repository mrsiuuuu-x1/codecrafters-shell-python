import sys


def main():
    # TODO: Uncomment the code below to pass the first stage
    while True:
        sys.stdout.write("$ ")
        command = input()
        if command[0:4] == "echo":
            print(f"{command[5:]}\n")
        if command == "exit":
            break


if __name__ == "__main__":
    main()
