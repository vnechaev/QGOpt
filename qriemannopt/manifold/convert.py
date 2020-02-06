import tensorflow as tf

@tf.function
def complex_to_real(tensor):
    """Returns tensor converted from complex tensor of shape
    (...,) to real tensor of shape (..., 2), where last index
    marks real [0] and imag [1] parts of complex valued tensor.
    Args:
        tensor: complex valued tf.Tensor of shape (...,)
    Returns:
        real valued tf.Tensor of shape (..., 2)"""
    return tf.concat([tf.math.real(tensor)[..., tf.newaxis],
                      tf.math.imag(tensor)[..., tf.newaxis]], axis=-1)


@tf.function
def real_to_complex(tensor):
    """Returns tensor converted from real tensor of shape
    (..., 2) to complex tensor of shape (...,), where last index
    of real tensor marks real [0] and imag [1]
    parts of complex valued tensor.
    Args:
        tensor: real valued tf.Tensor of shape (..., 2)
    Returns:
        complex valued tf.Tensor of shape (...,)"""
    return tf.complex(tensor[..., 0], tensor[..., 1])