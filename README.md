# Qiskit IBM Quantum Provider

[![License](https://img.shields.io/github/license/Qiskit/qiskit-ibm-provider.svg?style=popout-square)](https://opensource.org/licenses/Apache-2.0)
[![CI](https://github.com/Qiskit/qiskit-ibm-provider/actions/workflows/ci.yml/badge.svg)](https://github.com/Qiskit/qiskit-ibm-provider/actions/workflows/ci.yml)
[![](https://img.shields.io/github/release/Qiskit/qiskit-ibm-provider.svg?style=popout-square)](https://github.com/Qiskit/qiskit-ibm-provider/releases)
[![](https://img.shields.io/pypi/dm/qiskit-ibm-provider.svg?style=popout-square)](https://pypi.org/project/qiskit-ibm-provider/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Coverage Status](https://coveralls.io/repos/github/Qiskit/qiskit-ibm-provider/badge.svg?branch=main)](https://coveralls.io/github/Qiskit/qiskit-ibm-provider?branch=main)

**Qiskit** is an open-source SDK for working with quantum computers at the level of circuits, algorithms, and application modules.

This project contains a provider that allows accessing the **[IBM Quantum]**
systems and simulators.

## Migrating from qiskit-ibmq-provider

If you are familiar with the `qiskit-ibmq-provider` repository, check out the [migration guide].

## Installation

You can install the provider using pip:

```bash
pip install qiskit-ibm-provider
```

## Provider Setup

1. Create an IBM Quantum account or log in to your existing account by visiting the [IBM Quantum login page].

1. Copy (and/or optionally regenerate) your API token from your
   [IBM Quantum account page].

1. Take your token from step 2, here called `MY_API_TOKEN`, and save it by calling `IBMProvider.save_account()`:

   ```python
   from qiskit_ibm_provider import IBMProvider
   IBMProvider.save_account(token='MY_API_TOKEN')
   ```

   The command above stores your credentials locally in a configuration file called `qiskit-ibm.json`. By default, this file is located in `$HOME/.qiskit`, where `$HOME` is your home directory.
   Once saved you can then instantiate the provider like below and access the backends:

   ```python
   from qiskit_ibm_provider import IBMProvider
   provider = IBMProvider()

   # display current supported backends
   print(provider.backends())

   # get IBM's simulator backend
   simulator_backend = provider.get_backend('ibmq_qasm_simulator')
   ```

### Load Account from Environment Variables
Alternatively, the IBM Provider can discover credentials from environment variables:
```bash
export QISKIT_IBM_TOKEN='MY_API_TOKEN'
```

Then instantiate the provider without any arguments and access the backends:
```python
from qiskit_ibm_provider import IBMProvider
provider = IBMProvider()
```

### Enable Account for Current Session
As another alternative, you can also enable an account just for the current session by instantiating the provider with the token.

```python
from qiskit_ibm_provider import IBMProvider
provider = IBMProvider(token='MY_API_TOKEN')
```

## Next Steps

Now you're set up and ready to check out some of the tutorials.
- [Qiskit IBM Provider]
- [Qiskit]

## Contribution Guidelines

If you'd like to contribute to qiskit-ibm-provider, please take a look at our
[contribution guidelines]. This project adheres to Qiskit's [code of conduct].
By participating, you are expect to uphold to this code.

We use [GitHub issues] for tracking requests and bugs. Please use our [slack]
for discussion and simple questions. To join our Slack community use the
invite link at [Qiskit.org]. For questions that are more suited for a forum we
use the `Qiskit` tag in [Stack Exchange].

## Authors and Citation

The Qiskit IBM Quantum Provider is the work of [many people] who contribute to the
project at different levels. If you use Qiskit, please cite as per the included
[BibTeX file].

## License

[Apache License 2.0].


[IBM Quantum]: https://www.ibm.com/quantum-computing/
[IBM Quantum login page]:  https://quantum-computing.ibm.com/login
[IBM Quantum account page]: https://quantum-computing.ibm.com/account
[contribution guidelines]: https://github.com/Qiskit/qiskit-ibm-provider/blob/main/CONTRIBUTING.md
[code of conduct]: https://github.com/Qiskit/qiskit-ibm-provider/blob/main/CODE_OF_CONDUCT.md
[GitHub issues]: https://github.com/Qiskit/qiskit-ibm-provider/issues
[slack]: https://qiskit.slack.com
[Qiskit.org]: https://qiskit.org
[Stack Exchange]: https://quantumcomputing.stackexchange.com/questions/tagged/qiskit
[Qiskit Tutorial]: https://github.com/Qiskit/qiskit-tutorial
[many people]: https://github.com/Qiskit/qiskit-ibm-provider/graphs/contributors
[Qiskit IBM Provider]: https://github.com/Qiskit/qiskit-ibm-provider/tree/main/docs/tutorials
[Qiskit]: https://github.com/Qiskit/qiskit-tutorial
[BibTeX file]: https://github.com/Qiskit/qiskit/blob/master/Qiskit.bib
[Apache License 2.0]: https://github.com/Qiskit/qiskit-ibm-provider/blob/main/LICENSE.txt
[migration guide]: https://github.com/Qiskit/qiskit-ibm-provider/blob/main/docs/tutorials/Migration_Guide_from_qiskit-ibmq-provider.ipynb
