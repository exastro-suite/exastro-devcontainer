#!/bin/bash
#   Copyright 2026 NEC Corporation
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

echo "START $(basename $0)"

# Install the tools for development
which aws || {
    echo "Installing AWS CLI v2..."
    cd /tmp
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip -q awscliv2.zip
    sudo ./aws/install
    rm -rf /tmp/aws /tmp/awscliv2.zip
}

which claude || {
    echo "Installing Claude CLI..."
    cd /tmp
    curl -fsSL https://claude.ai/install.sh | bash
}

echo "FINISH $(basename $0)"
