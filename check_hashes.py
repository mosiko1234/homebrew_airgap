#!/usr/bin/env python3

hashes = [
    "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
    "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    "fedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321",
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
]

for i, hash_val in enumerate(hashes, 1):
    print(f"Hash {i}: {len(hash_val)} characters")
    if len(hash_val) != 64:
        print(f"  ERROR: Hash {i} is not 64 characters!")
    else:
        print(f"  OK: Hash {i} is exactly 64 characters")