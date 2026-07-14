"""Temporary diagnostic: inspect memory + result state for demo_user."""
from db import database

uid = "demo_user"

result = database.get_result(uid)
txns = (result or {}).get("transactions", [])
months = sorted({str(t.get("date",""))[:7] for t in txns})
print("=== active dashboard result ===")
print("num transactions:", len(txns))
print("months present:", months)

# Show subscription-like descriptions in the ACTIVE result
sub_hints = ("netflix","prime","hotstar","disney","spotify","subscription")
subs_in_result = [t.get("description") for t in txns
                  if any(h in (t.get("description","").lower()) for h in sub_hints)]
print("subscription-like descriptions in active result:", subs_in_result)

print("\n=== stored subscription memories ===")
for m in database.get_memories(uid):
    if m["kind"] == "subscription":
        print(" -", m["mem_key"], "|", m["content"], "| updated:", m["updated_at"])
