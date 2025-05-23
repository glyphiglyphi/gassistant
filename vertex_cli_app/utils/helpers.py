import re

def is_simple_query(query: str) -> bool:
    """
    Check if the query appears to be a simple calculation or non-search operation.
    Returns True if the query seems like it doesn't need a web search.
    (Migrated from gemini_cli_v8.py)
    """
    # Check for arithmetic operations/calculations
    calc_patterns = [
        r'\d+\s*[\+\-\*\/\%\^]\s*\d+',  # Basic arithmetic (3*3, 5+2, etc)
        r'calculate\s+',                 # Explicit calculation request
        r'compute\s+',                   # Explicit computation request
        r'solve\s+\d+',                  # Simple solve requests with numbers
        r'convert\s+\d+',                # Unit conversions
        r'factorial\s+of\s+\d+',         # Factorial calculations
        r'square\s+root\s+of\s+\d+',     # Square roots
    ]
    
    # Check for common question types that don't need search
    nonsearch_patterns = [
        r'^when\s+was\s+\d+',            # Simple historical questions like "when was 1999"
        r'^tell\s+me\s+a\s+joke',        # Joke requests
        r'^write\s+(a|me)\s+',           # Creative writing prompts
        r'^what\s+is\s+\d+\s*[\+\-\*\/]\s*\d+', # "What is 3*3" type questions
    ]
    
    # If any pattern matches, it's likely a simple query
    for pattern in calc_patterns + nonsearch_patterns:
        if re.search(pattern, query.lower()):
            return True
            
    return False

if __name__ == "__main__":
    queries_to_test = {
        "3*3": True,
        "calculate 5+2": True,
        "what is the capital of France": False,
        "search for cats": False,
        "tell me a joke": True,
        "when was 1999": True, # This was a non-search pattern
        "what is the weather like": False
    }
    print("--- Testing is_simple_query ---")
    all_passed = True
    for query, expected in queries_to_test.items():
        result = is_simple_query(query)
        match_status = result == expected
        print(f"Query: '{query}', Expected: {expected}, Got: {result}, Match: {match_status}")
        if not match_status:
            all_passed = False
            
    if all_passed:
        print("\nAll is_simple_query tests passed!")
    else:
        print("\nSome is_simple_query tests FAILED.")
