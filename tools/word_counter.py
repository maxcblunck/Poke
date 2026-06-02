import re
from collections import Counter

def count_words(text):
    words = re.findall(r"\b\w+\b", text.lower())
    return words, Counter(words)

def run():
    print("Word Counter — paste text, then press Enter twice.")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)

    text = " ".join(lines)
    if not text.strip():
        print("No text provided.")
        return

    words, counts = count_words(text)
    print(f"\nTotal words : {len(words)}")
    print(f"Unique words: {len(counts)}")
    print("\nTop 10 most common:")
    for word, freq in counts.most_common(10):
        print(f"  {word}: {freq}")

if __name__ == "__main__":
    run()
