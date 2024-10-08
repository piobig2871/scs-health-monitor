import logging

from behave import given, when, then
from kubernetes import client, config, stream, watch
import requests
from http import HTTPStatus

from container_level_testing.features.steps.services import create_service
from container_level_testing.features.steps.tools import get_node_port
from container_level_testing.features.steps.pods import check_if_pod_running, generate_pod_object


class KubernetesTestSteps:

    @given('a Kubernetes cluster')
    def kubernetes_cluster(context):
        """Given a Kubernetes cluster, this step initializes the Kubernetes client configuration and verifies
        connection to the cluster by listing the nodes.

        :param context: Behave context object
        """
        config.load_kube_config()
        context.v1 = client.CoreV1Api()

        # Setup logger
        context.logger = logging.Logger("kubernetes-runner")
        sh = logging.StreamHandler()
        shf = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        sh.setFormatter(shf)
        context.logger.addHandler(sh)

        # Set up other context objects
        context.response = None
        context.ping_response = None
        context.namespace = "scs-vp12"
        context.v1.list_node()
        result = context.v1.list_node()
        if not result:
            raise Exception(f"Failed to connect to Kubernetes cluster: {result.stderr}")

    @when('I create a container named {container_name}')
    def create_container(context, container_name):
        """
        When a container is created with the specified name, this step creates a pod
        in the default namespace and waits for it to start.

        :param context: Behave context object
        :param container_name: Name of the container to create
        """
        pod = generate_pod_object(pod_name=container_name)
        context.v1.create_namespaced_pod(namespace=context.namespace, body=pod)

        w = watch.Watch()
        for ev in w.stream(func=context.v1.list_namespaced_pod, namespace=context.namespace, timeout_seconds=10):
            obj = ev["object"]
            if obj.status.phase == "Running" and obj.metadata.name == container_name:
                context.logger.debug(f"Found container {container_name} running")
                w.stop()
                return

    @then('the container {container_name} should be running')
    def container_running(context, container_name):
        """
        Then the container should be running, this step checks if the specified container
        is in the running state.

        :param context: Behave context object
        :param container_name: Name of the container to check
        """
        assert check_if_pod_running(context.v1, container_name=container_name, namespace=context.namespace)

    @when('I create a service for the container named {container_name} on {port}')
    def create_service(context, container_name, port):
        """
        When a service is created for the specified container on the given port, this step
        defines and applies the service manifest.

        :param context: Behave context object
        :param container_name: Name of the container to create the service for
        :param port: Port number for the service
        """
        result = context.v1.create_namespaced_service(
            namespace=context.namespace, body=create_service(
                service_name=container_name, port=port))
        # Exception(f"Failed to create service: {result.stderr}")

    @then('the service for {container_name} should be running')
    def service_running(context, container_name):
        """
        Then the service should be running, this step verifies that the service
        for the specified container is running.

        :param context: Behave context object
        :param container_name: Name of the container whose service status is checked
        """
        service = context.v1.read_namespaced_service(name=container_name, namespace=context.namespace)
        assert service, f"Expected service {container_name} to be running"

    # @when('I send an HTTP request to {container_name}')
    # def send_http_request(context, container_name):
    #     result = subprocess.run(
    #         ["kubectl", "get", "service", container_name, "-o", "jsonpath='{.spec.clusterIP}'"],
    #         capture_output=True, text=True)
    #     if result.returncode != 0:
    #         raise Exception(f"Failed to get service IP: {result.stderr}")
    #     ip = result.stdout.strip().strip("'")
    #     context.response = requests.get(f"http://{ip}")

    @when('I send an HTTP request to {container_name} from outside the cluster using node IP node_ip')
    def send_http_request(context, container_name):
        """
        When an HTTP request is sent to the specified container via ingress, this step
        sends the request using the provided ingress host.

        :param context: Behave context object
        :param container_name: Name of the container to send the request to
        :param ingress_host: Ingress host to use for the request
        """
        service = context.v1.read_namespaced_service(name=container_name, namespace=context.namespace)
        node_ip = service.spec.cluster_ip
        node_port = get_node_port(client=context.v1, service_name=container_name, namespace=context.namespace)
        try:
            context.response = requests.get(f"http://{node_ip}:{node_port}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to send HTTP request: {e}")

    @given('a container running a web server named {container_name}')
    def container_running_web_server(context, container_name):
        """
        Given a container running a web server, this step creates and ensures the specified
        container is running.

        :param context: Behave context object
        :param container_name: Name of the web server container
        """
        context.create_container(context, container_name)
        context.container_running(context, container_name)

    @then('the response status code should be 200')
    def response_status_code(context):
        """
        Then the response status code should be 200, this step checks the HTTP response
        status code.

        :param context: Behave context object
        """
        assert context.response.status_code == HTTPStatus.OK

    @when('{src_container} pings {dst_container}')
    def ping(context, src_container, dst_container):
        """
        When one container pings another, this step executes a ping command from the source
        container to the destination container.

        :param context: Behave context object
        :param src_container: Name of the source container
        :param dst_container: Name of the destination container
        """
        try:
            pong_ip = context.v1.read_namespaced_pod(dst_container, namespace=context.namespace) \
                .status.pod_ip

            context.logger.debug(f"Got pong IP: {pong_ip}")

            exec_command = ['ping', '-c', '1', pong_ip]
            response = stream.stream(
                context.v1.connect_get_namespaced_pod_exec,
                name=src_container,
                namespace=context.namespace,
                command=exec_command,
                stderr=True, stdin=False,
                stdout=True, tty=False)
            context.ping_response = response

            if " 0% packet loss" not in response:
                raise Exception(f"Ping failed: {response}")
        except client.exceptions.ApiException as e:
            raise Exception(f"An error occurred during ping: {e}")

    @then('the ping should be successful')
    def ping_successful(context):
        """
        Then the ping should be successful, this step verifies that the ping command
        was successful.

        :param context: Behave context object
        """
        assert " 0% packet loss" in context.ping_response

    @when('I delete the container named {container_name}')
    def delete_container(context, container_name):
        """
        When a container is deleted, this step deletes the specified container from
        the default namespace.

        :param context: Behave context object
        :param container_name: Name of the container to delete
        """
        context.v1.delete_namespaced_pod(
            name=container_name,
            namespace=context.namespace,
            body=client.V1DeleteOptions(),
            async_req=True
        )

        w = watch.Watch()
        for ev in w.stream(func=context.v1.list_namespaced_pod, namespace=context.namespace, timeout_seconds=10):
            et = ev["type"]
            obj = ev["object"]

            if et == "DELETED" and obj.metadata.name == container_name:
                context.logger.debug(f"Found container {container_name} as DELETED")
                w.stop()
                return

    @then('the container {container_name} should be deleted')
    def container_deleted(context, container_name):
        """
        Then the container should be deleted, this step checks that the specified
        container has been deleted.

        :param context: Behave context object
        :param container_name: Name of the container to check
        """
        try:
            context.v1.read_namespaced_pod(name=container_name, namespace=context.namespace)
            raise AssertionError("Pod still exists")
        except client.exceptions.ApiException as e:
            if e.status == 404:
                pass
                # context.logger(f"Pod is successfully deleted")
            else:
                raise e

    @then('I delete the service named {service_name}')
    def delete_service(context, service_name):
        """
        Delete a Kubernetes service by its name.

        :param context: Behave context object
        :param service_name: Name of the service to be deleted
        """
        try:
            context.v1.delete_namespaced_service(name=service_name, namespace=context.namespace)
        except client.exceptions.ApiException as e:
            if e.status == 404:
                raise Exception(f"Service {service_name} not found: {e}")
            else:
                raise e
