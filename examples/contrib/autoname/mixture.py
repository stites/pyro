# Copyright (c) 2017-2019 Uber Technologies, Inc.
# SPDX-License-Identifier: Apache-2.0

import argparse

import torch
from torch.distributions import constraints

import pyro
import pyro.distributions as dist
from pyro.contrib.autoname import named
from pyro.infer import SVI, JitTrace_ELBO, Trace_ELBO
from pyro.optim import Adam

# This is a simple gaussian mixture model.
#
# The example demonstrates how to pass named.Objects() from a global model to
# a local model implemented as a helper function.


def model(data, k):
    latent = named.Object("latent")

    # Create parameters for a Gaussian mixture model.
    latent.probs.param_(torch.ones(k) / k, constraint=constraints.simplex)
    latent.locs.param_(torch.zeros(k))
    latent.scales.param_(torch.ones(k), constraint=constraints.positive)

    # Observe all the data. We pass a local latent in to the local_model.
    latent.local = named.List()
    for x in data:
        local_model(latent.local.add(), latent.probs, latent.locs, latent.scales, obs=x)


def local_model(latent, ps, locs, scales, obs=None):
    i = latent.id.sample_(dist.Categorical(ps))
    return latent.x.sample_(dist.Normal(locs[i], scales[i]), obs=obs)


def guide(data, k):
    latent = named.Object("latent")
    latent.local = named.List()
    for x in data:
        # We pass a local latent in to the local_guide.
        local_guide(latent.local.add(), k)


def local_guide(latent, k):
    # The local guide simply guesses category assignments.
    latent.probs.param_(torch.ones(k) / k, constraint=constraints.positive)
    latent.id.sample_(dist.Categorical(latent.probs))


def main(args):
    pyro.set_rng_seed(0)

    optim = Adam({"lr": 0.1})
    elbo = JitTrace_ELBO() if args.jit else Trace_ELBO()
    inference = SVI(model, guide, optim, loss=elbo)
    data = torch.tensor([0.0, 1.0, 2.0, 20.0, 30.0, 40.0])
    k = 2

    print("Step\tLoss")
    loss = 0.0
    for step in range(args.num_epochs):
        if step and step % 10 == 0:
            print("{}\t{:0.5g}".format(step, loss))
            loss = 0.0
        loss += inference.step(data, k=k)

    print("Parameters:")
    for name, value in sorted(pyro.get_param_store().items()):
        print("{} = {}".format(name, value.detach().cpu().numpy()))


if __name__ == "__main__":
    assert pyro.__version__.startswith("1.7.0")
    parser = argparse.ArgumentParser(description="parse args")
    parser.add_argument("-n", "--num-epochs", default=200, type=int)
    parser.add_argument("--jit", action="store_true")
    args = parser.parse_args()
    main(args)
