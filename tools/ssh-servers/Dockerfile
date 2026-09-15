FROM registry.access.redhat.com/ubi9/ubi-init:9.4

ARG SSH_USER_NAME=sshuser
ARG SSH_USER_PASSWORD=password

RUN --mount=type=secret,id=host_certificate_file,dst=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem \
    printf '%s\n' \
    "http_proxy=${http_proxy}" \
    "https_proxy=${https_proxy}" \
    "no_proxy=${no_proxy}" \
    "HTTP_PROXY=${http_proxy}" \
    "HTTPS_PROXY=${https_proxy}" \
    "NO_PROXY=${no_proxy}" \
    >> /etc/environment

RUN --mount=type=secret,id=host_certificate_file,dst=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem \
    dnf install -y openssh-server openssh-clients passwd sudo python3 \
    && dnf clean all \
    && ssh-keygen -A

# firewalld はサブスクリプション必須で UBI/EPEL に無いため、CentOS Stream 9 の
# BaseOS リポジトリから一時的に取得する。取得後はリポジトリ定義を削除する。
RUN --mount=type=secret,id=host_certificate_file,dst=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem \
    printf '%s\n' \
    '[centos-stream-baseos]' \
    'name=CentOS Stream 9 - BaseOS' \
    'baseurl=https://mirror.stream.centos.org/9-stream/BaseOS/$basearch/os/' \
    'gpgcheck=0' \
    'enabled=1' \
    > /etc/yum.repos.d/centos-stream-baseos.repo

#     && dnf install -y --disablerepo='*' --enablerepo='centos-stream-baseos' firewalld \
#     && rm -f /etc/yum.repos.d/centos-stream-baseos.repo \
#     && dnf clean all

RUN --mount=type=secret,id=host_certificate_file,dst=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem \
    printf '%s\n' \
    'Defaults env_keep += "http_proxy https_proxy no_proxy HTTP_PROXY HTTPS_PROXY NO_PROXY"' \
    > /etc/sudoers.d/proxy-env \
    && chmod 440 /etc/sudoers.d/proxy-env

RUN useradd -m "${SSH_USER_NAME}" \
    && echo "${SSH_USER_NAME}:${SSH_USER_PASSWORD}" | chpasswd \
    && usermod -aG wheel "${SSH_USER_NAME}" \
    && echo "${SSH_USER_NAME} ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/99-nopasswd \
    && chmod 440 /etc/sudoers.d/99-nopasswd

# RUN systemctl enable sshd firewalld \
#     && firewall-offline-cmd --add-service=ssh

EXPOSE 22

CMD ["/usr/sbin/init"]
