import inspect
import functools


def checktypes(func):
    '''Decorator to verify arguments and return types

    Example:

        >>> @checktypes
        ... def test(a:int, b:str) -> int:
        ...     return int(a * b)

        >>> test(10, '1')
        1111111111

        >>> test(10, 1)
        Traceback (most recent call last):
          ...
        ValueError: foo: wrong type of 'b' argument, 'str' expected, got 'int'
    '''

    sig = inspect.signature(func)

    types = {}
    for param in sig.parameters.values():
        # Iterate through function's parameters and build the list of
        # arguments types
        type_ = param.annotation
        if type_ is param.empty or not inspect.isclass(type_):
            # Missing annotation or not a type, skip it
            continue

        types[param.name] = type_

        # If the argument has a type specified, let's check that its
        # default value (if present) conforms with the type.
        if param.default is not param.empty and not isinstance(param.default, type_):
            raise ValueError("{func}: wrong type of a default value for {arg!r}". \
                             format(func=func.__qualname__, arg=param.name))

    def check_type(sig, arg_name, arg_type, arg_value):
        # Internal function that encapsulates arguments type checking
        if not isinstance(arg_value, arg_type):
            raise ValueError("{func}: wrong type of {arg!r} argument, " \
                             "{exp!r} expected, got {got!r}". \
                             format(func=func.__qualname__, arg=arg_name,
                                    exp=arg_type.__name__, got=type(arg_value).__name__))

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Let's bind the arguments
        ba = sig.bind(*args, **kwargs)
        for arg_name, arg in ba.arguments.items():
            # And iterate through the bound arguments
            try:
                type_ = types[arg_name]
            except KeyError:
                continue
            else:
                # OK, we have a type for the argument, lets get the corresponding
                # parameter description from the signature object
                param = sig.parameters[arg_name]
                if param.kind == param.VAR_POSITIONAL:
                    # If this parameter is a variable-argument parameter,
                    # then we need to check each of its values
                    for value in arg:
                        check_type(sig, arg_name, type_, value)
                elif param.kind == param.VAR_KEYWORD:
                    # If this parameter is a variable-keyword-argument parameter:
                    for subname, value in arg.items():
                        check_type(sig, arg_name + ':' + subname, type_, value)
                else:
                    # And, finally, if this parameter a regular one:
                    check_type(sig, arg_name, type_, arg)

        result = func(*ba.args, **ba.kwargs)

        # The last bit - let's check that the result is correct
        '''
        return_type = sig.return_annotation
        if (return_type is not sig._empty and
                isinstance(return_type, type) and
                not isinstance(result, return_type)):

            raise ValueError('{func}: wrong return type, {exp} expected, got {got}'. \
                             format(func=func.__qualname__, exp=return_type.__name__,
                                    got=type(result).__name__))
        '''
        return result

    return wrapper