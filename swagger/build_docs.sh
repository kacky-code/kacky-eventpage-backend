#!/bin/bash

# Check if npx is installed
if ! [ -x "$(command -v npx)" ]; then
    echo 'Error: npx is not installed.' >&2
    exit 1
fi

# Check if openapi.yaml exists
if ! [ -f "openapi.yaml" ]; then
    echo 'Error: openapi.yaml does not exist.' >&2
    echo 'Exiting...'
    exit 1
fi

npx @redocly/cli build-docs -o index.html openapi.yaml
