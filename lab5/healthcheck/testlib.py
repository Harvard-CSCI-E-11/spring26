"""
testlib support for healtchecks.
"""




from functools import wraps

registry = []

def testcase(name, description):
    def decorator(fn):
        @wraps(fn)
        def wrapper():
            return fn()
        wrapper._metadata = {
            'name': name,
            'description': description
        }
        registry.append(wrapper)
        return wrapper
    return decorator
