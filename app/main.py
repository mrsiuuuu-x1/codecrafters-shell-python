import sys

BUILTIN ={"exit","echo","type"}

def main():
    # TODO: Uncomment the code below to pass the first stage
    while True:
        sys.stdout.write("$ ")
        command = input().strip()
        if not command:
            continue

        if command.startswith("echo"):
            print(command[5:])
        elif command.startswith("exit"):
            break
        elif command.startswith("type "):
            target = command[5:]
            if target in BUILTIN:
                print(f"{command[5:]} is a shell builtin")
            else:
                print(f"{command[5:]}: not found")
        else:
            print(f"{command}: command not found")


if __name__ == "__main__":
    main()
