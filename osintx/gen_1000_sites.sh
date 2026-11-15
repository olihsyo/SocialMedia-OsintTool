#!/usr/bin/env bash

CSV_FILE="netapi-top-websites-bd-2026-10.csv"
OUT="$HOME/osintx/sites.yaml"

if [ ! -f "$CSV_FILE" ]; then
    echo -e "\033[31m[-] Error: $CSV_FILE not found in current directory.\033[0m"
    exit 1
fi

echo -e "\033[36m[*] Parsing $CSV_FILE and generating sites.yaml...\033[0m"

cat << 'YAML' > $OUT
# Massive OSINT Registry (Generated from NetAPI Top 1000 BD)
# Type: status | regex | absent_regex | json | redirect
# Weight: 1-10 (Reliability)

YAML

# CSV ফাইল থেকে ডোমেইন কলাম ($2) রিড করা, হেডার বাদ দেওয়া
tail -n +2 "$CSV_FILE" | while IFS=, read -r rank domain; do
    # স্পেস বা ক্যারেজ রিটার্ন রিমুভ করা
    domain=$(echo "$domain" | tr -d '\r' | xargs)
    
    # ফাঁকা লাইন স্কিপ করা
    if [ -z "$domain" ]; then continue; fi

    # ডোমেইন থেকে মেইন নাম বের করা (যেমন: google.com থেকে Google)
    name=$(echo "$domain" | cut -d'.' -f1 | sed 's/^./\U&/')

    # জেনেরিক ইমেইল/ইউজারনেম এন্ডপয়েন্ট প্যাটার্ন (যেহেতু সবার আসল এপিআই জানা নেই)
    cat << YAML >> $OUT
- name: $name
  kinds: [email]
  url: https://$domain/api/v1/auth/check?email=%s
  type: regex
  expect: '(exists|taken|found|true)'
  weight: 4
  
- name: $name (User)
  kinds: [username]
  url: https://$domain/$s
  type: status
  expect: "200"
  weight: 3

YAML
done

echo -e "\033[32m[+] Generated $(grep -c "^- name:" $OUT) site rules in $OUT\033[0m"
