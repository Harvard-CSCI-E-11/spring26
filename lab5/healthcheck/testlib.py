"""
testlib support for healtchecks.

registry is an array of functions that registered themsevles with the @testcase decorator.
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
