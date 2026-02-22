# Test bucket logic
forecast = 38

# Bucket <38°F
bucket_min = -999
bucket_max = 38

in_bucket = bucket_min <= forecast <= bucket_max
print(f"Forecast: {forecast}°F")
print(f"Bucket: <{bucket_max}°F (strictly less)")
print(f"Logic check: {bucket_min} <= {forecast} <= {bucket_max}")
print(f"In bucket: {in_bucket}")
print()

# But wait, "<38" means strictly less than 38
# So the range should be (-999, 37]
print("Correct interpretation:")
print("  '<38°' means temp < 38, so max is 37 (inclusive)")
correct_max = 37
in_bucket_correct = bucket_min <= forecast <= correct_max
print(f"  In bucket (<38): {in_bucket_correct}")
