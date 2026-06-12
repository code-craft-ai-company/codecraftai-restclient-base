=================================
Code Craft AI RestClient Base
=================================

The ``codecraftai-restclient-base`` package is the foundation for the REST-client packages in the ccai suite. It provides the common base classes and utilities that derived clients (for example ``codecraftai-restclient-github-public`` and ``codecraftai-gitlab``) build on, so that every REST integration has the same shape for pagination, schema handling, aspects, and code generation.

Highlights
==========

- ``RestClientBase`` as the HTTP client root.
- ``RestApiGroup`` for grouping endpoints into logical API surfaces.
- ``PagedList`` and ``ItemsResult`` for iteration over paginated responses.
- ``SchemaObject`` and ``SchemaField`` as the serialization base for response models.
- ``RestClientGenerator`` for generating typed client code from an OpenAPI-style spec.
- ``AspectsRest`` as the REST-specific incarnation of the ``Aspects`` pattern.

Repository Structure
====================

- ``development/`` - Runtime environment scripts.
- ``repository-setup/`` - Repository homing and setup scripts.
- ``source/packages/`` - Package source code.
- ``source/testroots/ccai/`` - TestBase test roots.
- ``userguide/`` - Standards, conventions, and documentation.

Environment Setup
=================

When working in a Codex container:

.. code-block:: bash

   ./development/setup-agent-container

For local development:

.. code-block:: bash

   ./repository-setup/rehome-repository
   ./development/setup-environment

Running Tests
=============

Activate the virtual environment:

.. code-block:: bash

   source .venv/bin/activate

Run the single-host test suite:

.. code-block:: bash

   testbase testing run --root source/testroots/ccai --includes=ccai.tests.restclient.base --output=./.output

Standards and Conventions
=========================

- Naming conventions: ``userguide/10-02-naming-conventions.rst``
- Code organization: ``userguide/10-01-code-organization.rst``
- Coding standards: ``userguide/10-00-coding-standards.rst``

Additional Resources
====================

- User guide entry point: ``userguide/userguide.rst``
