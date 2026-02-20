import sys
import shutil
import os

BUILTIN = {"exit", "echo", "type"}

def main():
    while True:
        sys.stdout.write("$ ")
        command = input().strip()  
        if not command:
            continue
        if command.startswith("echo "):
            print(command[5:])      
        elif command.startswith("exit"):
            break     
        elif command.startswith("type "):
            target = command[5:]
            if target in BUILTIN:
                print(f"{target} is a shell builtin")
            else:
                found_path = shutil.which(target)
                if found_path:
                    print(f"{target} is {found_path}")
                else:
                    print(f"{target}: not found")               
        else:
            print(f"{command}: command not found")

if __name__ == "__main__":
    main()