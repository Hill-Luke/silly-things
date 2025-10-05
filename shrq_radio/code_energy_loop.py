import subprocess

# Path to your text file containing all MP3 paths (one per line)
file_list_path = "/media/lukeofthehill/jukebox/silly-things/filepaths.txt"

# Read filepaths and strip whitespace/newlines
with open(file_list_path, "r") as f:
    filepaths = [line.strip() for line in f if line.strip()]

# # Loop through and call your existing energy_tagger.py

# print('Formatting the filepaths')
# formatted_paths=[]
# for path in filepaths:
#     quoted_path = f'"{path}"'
#     formatted_paths.append(quoted_path)


print("Analyzing BPM")
for fp in filepaths:

    print(f"\n🎧 Tagging: {fp}")
    subprocess.run(["python", "energy_distr.py", fp], check=False)

