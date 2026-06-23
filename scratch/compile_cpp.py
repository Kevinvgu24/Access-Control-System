import subprocess
import os

def compile_cpp():
    cwd = "/home/kevinvgu/Access-Control-System-main/src/Native_Tappas_CPP"
    build_dir = os.path.join(cwd, "build")
    
    # Run cmake
    print("--- Running CMake ---")
    res = subprocess.run(["cmake", "."], cwd=cwd, capture_output=True, text=True)
    print("Stdout:")
    print(res.stdout)
    if res.returncode != 0:
        print("Stderr:")
        print(res.stderr)
        return False
        
    # Run make
    print("\n--- Running Make ---")
    res = subprocess.run(["make"], cwd=build_dir if os.path.exists(build_dir) else cwd, capture_output=True, text=True)
    print("Stdout:")
    print(res.stdout)
    if res.returncode != 0:
        print("Stderr:")
        print(res.stderr)
        return False
        
    print("\nCompilation completed successfully!")
    return True

if __name__ == "__main__":
    compile_cpp()
