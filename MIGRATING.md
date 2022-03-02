# Migrating from qiskit-ibmq-provider

## Installation
The Qiskit IBM Provider is now distributed as a separate PyPI package called `qiskit-ibm-provider`. You can install the provider using pip:

```bash
pip install qiskit-ibm-provider
```

Note: `qiskit-ibm-provider` is not part of the `qiskit` meta package and hence will not be included when you `pip install qiskit`.

## Breaking Changes
1. The `IBMQ` global variable which was an instance of the `IBMQFactory` has been removed.
1. `IBMQFactory` and `AccountProvider` classes have been removed and the functionality provided by these two classes have been combined and refactored in the new `IBMProvider` class. This class will provide a simplified interface as shown below and serve as the entrypoint going forward.

   | Method / Constructor | Description |
   |--------|-------------|
   | IBMProvider.save_account(TOKEN, HUB, GROUP, PROJECT) | Save your account to disk for future use and optionally set a default hub/group/project to be used when loading your account. |
   | IBMProvider() | Load account using saved credentials. |
   | IBMProvider.saved_account() | View the account saved to disk. |
   | IBMProvider.delete_account() | Delete the saved account from disk. |
   | IBMProvider(TOKEN) | Enable your account in the current session. |
   | IBMProvider.active_account() | List the account currently active in the session. |

1. `IBMBackend.run()`, formerly `IBMQBackend.run()`, now splits a long list of circuits into multiple jobs and manages them for you, replacing the
`IBMQJobManager` feature that was in `qiskit-ibmq-provider`. Instead of initializing a separate `IBMQJobManager`
instance, you can now pass a long list of circuits directly to `IBMBackend.run()` and receive an
`IBMCompositeJob` instance back. This `IBMCompositeJob` is a subclass of `IBMJob` and supports the
same methods as a "traditional" job.

Follow the provider setup instructions in the [README] to learn more.

A lot of other classes have been renamed but may not be directly used by most users. Please see the [Appendix](#class-name-changes) for a complete list.

## Migrating your existing code

Use the examples below to migrate your existing code:

### Load Account using Saved Credentials

Before
```python
from qiskit import IBMQ
IBMQ.save_account(token='MY_API_TOKEN')
provider = IBMQ.load_account() # loads saved account from disk
```
After
```python
from qiskit_ibm_provider import IBMProvider
IBMProvider.save_account(token='MY_API_TOKEN')
provider = IBMProvider() # loads saved account from disk
```

### Load Account using Environment Variables

Before
```bash
export QE_TOKEN='MY_API_TOKEN'
```
```python
from qiskit import IBMQ
provider = IBMQ.load_account() # loads account from env variables
```
After
```bash
export QISKIT_IBM_API_TOKEN='MY_API_TOKEN'
```
```python
from qiskit_ibm_provider import IBMProvider
provider = IBMProvider() # loads account from env variables
```

### Saved Account

Before
```python
from qiskit import IBMQ
IBMQ.stored_account() # get saved account from qiskitrc file

# {'token': 'MY_API_TOKEN',
#  'url': 'https://auth.quantum-computing.ibm.com/api'}
```
After
```python
from qiskit_ibm_provider import IBMProvider
IBMProvider.saved_account() # get saved account from qiskitrc file

# {'token': 'MY_API_TOKEN',
#  'url': 'https://auth.quantum-computing.ibm.com/api'}
```

### Delete Account

Before
```python
from qiskit import IBMQ
IBMQ.delete_account() # delete saved account from qiskitrc file
```
After
```python
from qiskit_ibm_provider import IBMProvider
IBMProvider.delete_account() # delete saved account from qiskitrc file
```

### Enable Account

Before
```python
from qiskit import IBMQ
provider = IBMQ.enable_account(token='MY_API_TOKEN') # enable account for current session
```
After
```python
from qiskit_ibm_provider import IBMProvider
provider = IBMProvider(token='MY_API_TOKEN') # enable account for current session
```

### Active Account

Before
```python
from qiskit import IBMQ
provider = IBMQ.load_account() # load saved account
IBMQ.active_account() # check active account

# {'token': 'MY_API_TOKEN',
#  'url': 'https://auth.quantum-computing.ibm.com/api'}
```
After
```python
from qiskit_ibm_provider import IBMProvider
provider = IBMProvider() # load saved account
IBMProvider.active_account() # check active account

# {'token': 'MY_API_TOKEN',
#  'url': 'https://auth.quantum-computing.ibm.com/api'}
```

### Job Manager

Before
```python
from qiskit.providers.ibmq.managed import IBMQJobManager

job_manager = IBMQJobManager()
job_set = job_manager.run(long_list_of_circuits, backend=backend)
results = job_set.results()
```

After
```python
job = backend.run(long_list_of_circuits)
result = job.result()
```

## Clean up
1. Uninstall `qiskit-ibmq-provider`:

    ```bash
    pip uninstall qiskit-ibmq-provider
    ```
2. If you are using any of the below environment variables, please rename them.

    | Old Name  | New Name |
    | ------------- | ------------- |
    | QE_TOKEN | QISKIT_IBM_API_TOKEN |
    | QE_URL | QISKIT_IBM_API_URL |
    | QE_HUB | QISKIT_IBM_HUB |
    | QE_GROUP | QISKIT_IBM_GROUP |
    | QE_PROJECT | QISKIT_IBM_PROJECT |

    If you are a contributor or internal user of Qiskit IBM Provider please see the [Appendix](#appendix) for a complete list of environment variable changes.

## Appendix
### Class Name changes

| Old Name  | New Name |
| ------------- | ------------- |
| IBMQ  | IBMProvider  |
| IBMQFactory  | None (Removed) |
| AccountProvider  | None (Removed) |
| IBMQBackend  | IBMBackend |
| IBMQBackendService  | IBMBackendService |
| IBMQJob  | IBMJob |
| IBMQError | IBMError |
| IBMQProviderError | IBMProviderError |
| IBMQAccountError | None (Removed) |
| IBMQAccountValueError | IBMProviderValueError |
| IBMQAccountCredentialsNotFound | IBMProviderCredentialsNotFound |
| IBMQAccountCredentialsInvalidFormat | IBMProviderCredentialsInvalidFormat |
| IBMQAccountCredentialsInvalidToken | IBMProviderCredentialsInvalidToken |
| IBMQAccountCredentialsInvalidUrl | IBMProviderCredentialsInvalidUrl |
| IBMQAccountMultipleCredentialsFound | IBMProviderMultipleCredentialsFound |
| IBMQBackendError | IBMBackendError |
| IBMQBackendApiProtocolError | IBMBackendApiProtocolError |
| IBMQBackendValueError | IBMBackendValueError |
| IBMQBackendJobLimitError | IBMBackendJobLimitError |
| IBMQInputValueError | IBMInputValueError |
| IBMQNotAuthorizedError | IBMNotAuthorizedError |
| IBMQApiError | IBMApiError |
| IBMQJobError | IBMJobError |
| IBMQJobApiError | IBMJobApiError |
| IBMQJobFailureError | IBMJobFailureError |
| IBMQJobInvalidStateError | IBMJobInvalidStateError |
| IBMQJobTimeoutError | IBMJobTimeoutError |
| WebsocketIBMQProtocolError | WebsocketIBMProtocolError |
| ApiIBMQProtocolError | ApiIBMProtocolError |

### Environment Variable changes

| Old Name  | New Name |
| ------------- | ------------- |
| QE_TOKEN | QISKIT_IBM_API_TOKEN |
| QE_URL | QISKIT_IBM_API_URL |
| QE_HUB | QISKIT_IBM_HUB |
| QE_GROUP | QISKIT_IBM_GROUP |
| QE_PROJECT | QISKIT_IBM_PROJECT |
| QE_HGP | QISKIT_IBM_HGP |
| QE_PRIVATE_HGP | QISKIT_IBM_PRIVATE_HGP |
| QE_DEVICE | QISKIT_IBM_DEVICE |
| USE_STAGING_CREDENTIALS | QISKIT_IBM_USE_STAGING_CREDENTIALS |
| QE_STAGING_TOKEN | QISKIT_IBM_STAGING_API_TOKEN |
| QE_STAGING_URL | QISKIT_IBM_STAGING_API_URL |
| QE_STAGING_HGP | QISKIT_IBM_STAGING_HGP |
| QE_STAGING_PRIVATE_HGP | QISKIT_IBM_STAGING_PRIVATE_HGP |
| QE_STAGING_DEVICE | QISKIT_IBM_STAGING_DEVICE |
| TWINE_PASSWORD | PYPI_API_TOKEN |

[README]: https://github.com/Qiskit-Partners/qiskit-ibm/blob/main/README.md