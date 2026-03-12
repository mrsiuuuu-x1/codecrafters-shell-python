import sys
import shutil
import os
import subprocess

BUILTIN = {"exit", "echo", "type", "pwd", "cd"}

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
        elif command == "pwd":
            print(os.getcwd())
        elif command.startswith("cd "):
            path = command[3:].strip()
            path = os.path.expanduser(path)
            try:
                os.chdir(path)
            except FileNotFoundError:
                print(f"cd: {path}: No such file or directory")
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
            parts = command.split() 
            exe_name = parts[0]
            if shutil.which(exe_name):
                subprocess.run(parts)
            else:
                print(f"{command}: command not found")

if __name__ == "__main__":
    main()