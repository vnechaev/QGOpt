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


@tf.function
def egrad_to_rgrad(u, egrad):
    """Returns riemannian gradient from euclidean gradient.
    Equivalent to the projection of gradient on tangent
    space of Stiefel manifold
    Args:
        u: complex valued tf.Tensor of shape (..., q, p),
        points on Stiefel manifold.
        egrad: complex valued tf.Tensor of shape (..., q, p),
        gradients calculated at corresponding manifold points.
    Returns:
        tf.Tensor of shape (..., q, p), batch of projected matrices."""

    return 0.5 * u @ (tf.linalg.adjoint(u) @ egrad -\
                      tf.linalg.adjoint(egrad) @ u) +\
    (tf.eye(u.shape[-2], dtype=u.dtype) - u @ tf.linalg.adjoint(u)) @ egrad


@tf.function
def canonical_metric(v1, v2, u):
    """Returns g(v1, v2)_u, where g -- canonical metric,
    v1 and v2 vectors from tangent space and u is a point on
    a manifold.
    Args:
        v1: complex valued tf.Tensor of shape (..., q, p), first vector.
        v2: complex valued tf.Tensor of shape (..., q, p), second vector.
        u: complex valued tf.Tensor of shape (..., q, p), points on a manifold
    Returns:
        g(v1, v2)_u complex valued tf.Tensor of shape (1,)"""

    ker = tf.eye(u.shape[-2], dtype=u.dtype) - 0.5 * u @ tf.linalg.adjoint(u)
    return tf.reduce_sum(tf.linalg.trace(tf.linalg.adjoint(v1) @ ker @ v2))


@tf.function
def proj(u, vec):
    """Returns projection of vector on tangen space of Stiefel manifold.
    Args:
        u: complex valued tf.Tensor of shape (..., q, p), points on a manifold
        vec: complex valued tf.Tensor of shape (..., q, p),
        vectors to be projected
    Returns:
        complex valued tf.Tensor of shape (..., q, p) -- projected vector"""

    return 0.5 * u @ (tf.linalg.adjoint(u) @ vec -\
                      tf.linalg.adjoint(vec) @ u) +\
    (tf.eye(u.shape[-2], dtype=u.dtype) - u @ tf.linalg.adjoint(u)) @ vec


@tf.function
def retraction(v):
    """Maps arbitrary point from R^(q, p) back on Stiefel manifold.
    Args:
        v: complex valued tf.Tensor of shape (..., q, p), point to be mapped.
    Returns tf.Tensor of shape (..., q, p) point on Stiefel manifold"""

    _, u, w = tf.linalg.svd(v)
    return u @ tf.linalg.adjoint(w)


@tf.function
def vector_transport(u, vec):
    """Returns vector tranported to a new point u.
    This function is entirely equivalent to the projection on 
    the tangent space of u.
    Args:
        u: complex valued tf.Tensor of shape (..., q, p), points on a manifold
        vec: complex valued tf.Tensor of shape (..., q, p),
        vectors to be transported
    Returns:
        complex valued tf.Tensor of shape (..., q, p) -- transported vector"""

    return proj(u, vec)


class StiefelSGD(tf.optimizers.Optimizer):

    def __init__(self,
               learning_rate=0.01,
               momentum=0.0,
               name="StiefelSGD"):
        """Constructs a new Stochastic Gradient Descent optimizer on Stiefel
        manifold.
        Comment:
            The StiefelSGD works only with real valued tf.Variable of shape
            (..., q, p, 2), where ... -- enumerates manifolds 
            (can be either empty or any shaped),
            q and p size of an isometric matrix, the last index marks
            real and imag parts of an isometric matrix
            (0 -- real part, 1 -- imag part)
        Args:
            learning_rate: floating point number. The learning rate.
            Defaults to 0.01.
            name: Optional name prefix for the operations created when applying
            gradients.  Defaults to 'StiefelSGD'."""
        
        super(StiefelSGD, self).__init__(name)
        self._lr = learning_rate
        self._lr_t = self._lr_t = tf.convert_to_tensor(self._lr, name="learning_rate")
        self._momentum = False
        if isinstance(momentum, tf.Tensor) or callable(momentum) or momentum > 0:
            self._momentum = True
        if isinstance(momentum, (int, float)) and (momentum < 0 or momentum > 1):
            raise ValueError("`momentum` must be between [0, 1].")
        self.momentum = momentum


    def _create_slots(self, var_list):
        # create momentum slot if necessary
        if self._momentum:
            for var in var_list:
                self.add_slot(var, "momentum")


    def _resource_apply_dense(self, grad, var):

        #Complex version of grad and var
        complex_var = real_to_complex(var)
        complex_grad = real_to_complex(grad)

        #tf version of learning rate
        lr_t = tf.cast(self._lr_t, complex_var.dtype)

        #Riemannian gradient
        grad_proj = egrad_to_rgrad(complex_var, complex_grad)

        #Upadte of vars (step and retraction)
        if self._momentum:
            #Update momentum
            momentum_var = self.get_slot(var, "momentum")
            momentum_complex = real_to_complex(momentum_var)
            momentum_complex = self.momentum * momentum_complex +\
            (1 - self.momentum) * grad_proj

            #New value of var
            new_var = complex_var - lr_t * momentum_complex
            new_var = retraction(new_var)

            #Momentum transport
            momentum_complex = vector_transport(new_var, momentum_complex)
            momentum_var.assign(complex_to_real(momentum_complex))
        else:
            #New value of var
            new_var = complex_var - lr_t * grad_proj
            new_var = retraction(new_var)

        #Update of var
        var.assign(complex_to_real(new_var))

    def _resource_apply_sparse(self, grad, var):
        raise NotImplementedError("Sparse gradient updates are not supported.")
    
    def get_config(self):
        config = super(StiefelSGD, self).get_config()
        config.update({
            "learning_rate": self._lr,
            "momentum": self.momentum
        })
        return config
