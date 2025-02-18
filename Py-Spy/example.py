def process_data():
    data = [x * 2 for x in range(100000)]
    return sum(data)

def generate_report():
    result = process_data()
    print(f"Result: {result}")

generate_report()