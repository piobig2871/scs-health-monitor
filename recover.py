import openstack
from libs.loggerClass import Logger
from tkinter import messagebox


class Recover:
    def __init__(self, cloud='gx', env_file_path="env.yaml"):
        self.conn = self._connect(cloud)
        self.log = Logger(name="inspector_logger", log_file="logfile.log")
        self.logger_instance = self.log.instance
        self.show_confirmation_popup()

    @staticmethod
    def show_confirmation_popup():
        result = messagebox.askyesno(
            "Confirmation",
            "Do you want to proceed with the deletion of all resources?")
        if result:
            print("User clicked Yes")
        else:
            print("User clicked No")
            exit()

    def _connect(self, cloud):
        return openstack.connection.from_config(cloud_name=cloud)

    def delete_networks(self):
        try:
            for network in self.conn.network.networks():
                for port in self.conn.network.ports(network_id=network.id):
                    self.conn.network.delete_port(port.id)
                    self.logger_instance.info(f"Port {port.id} deleted.")
                self.conn.network.delete_network(network.id)
                self.logger_instance.info(f"Network with ID {network.id} has been deleted.")
        except Exception as e:
            self.logger_instance.info(f"network {network.name} can't be deleted because exception {e} is raised.")

    def delete_subnets(self):
        for subnet in self.conn.network.subnets():
            try:
                self.delete_subent_ports(subnet=subnet)
                self.conn.network.delete_subnet(subnet.id)
                self.logger_instance.info(f"Subnet with ID {subnet.id} has been deleted.")
            except Exception as e:
                self.logger_instance.info(f"subnet {subnet.name} can't be deleted because exception {e} is raised.")

    def delete_security_groups(self):
        for group in self.conn.network.security_groups():
            try:
                self.conn.network.delete_security_group(group.id)
                self.logger_instance.info(f"Security group with ID {group.id} has been deleted.")
            except Exception as e:
                self.logger_instance.info(
                    f"security group {group.name} can't be deleted because exception {e} is raised.")

    def delete_security_group_rules(self):
        for rule in self.conn.network.security_group_rules():
            try:
                self.conn.network.delete_security_group_rule(rule.id)
                self.logger_instance.info(f"Security group rule with ID {rule.id} has been deleted.")
            except Exception as e:
                self.logger_instance.info(
                    f"security group rule {rule.name} can't be deleted because exception {e} is raised.")

    def delete_routers(self):
        for router in self.conn.network.routers():
            try:
                self.delete_ports_router(router=router)
                self.conn.network.delete_router(router.id)
                self.logger_instance.info(f"Router with ID {router.id} has been deleted.")
            except Exception as e:
                self.logger_instance.error(f"router {router.name} can't be deleted because exception {e} is raised.")

    def get_jumphosts(self):
        jumphosts = []
        for server in self.conn.compute.servers():
            if 'jumphost' in server.name.lower():
                jumphosts.append(server)
        return jumphosts

    def delete_jumphosts(self):
        for jumphost in self.get_jumphosts():
            self.conn.compute.delete_server(jumphost.id)

    def delete_ports_router(self, router):
        for port in self.conn.network.ports(device_id=router.id):
            try:
                self.conn.network.remove_interface_from_router(router.id, port_id=port.id)
                self.logger_instance.info(f"Port {port.id} detached from router {router.id}")
            except Exception as e:
                self.logger_instance.error(f"Port {port.name} can't be deleted because exception {e} is raised.")

    def delete_subent_ports(self, subnet):
        for port in self.conn.network.ports(network_id=subnet.id):
            for fixed_ip in port.fixed_ips:
                if fixed_ip['subnet_id'] == subnet.id:
                    try:
                        self.conn.network.delete_port(port.id)
                        self.logger_instance.info(f"Port {port.id} deleted.")
                    except Exception as e:
                        self.logger_instance.error(
                            f"subnet {subnet.name} can't be deleted because exception {e} is raised.")

    def delete_availability_zone(self, zone):
        try:
            self.conn.compute.delete_availability_zone(name=zone.name)
            self.logger_instance.info(f"Availability zone {zone.name} is deleted")
        except Exception as e:
            self.logger_instance.error(
                f"availability zone {zone.name} can't be deleted because exception {e} is raised.")

    def delete_availability_zones(self):
        for zone in self.conn.compute.availability_zones():
            self.delete_availability_zone(name=zone.name)

    def delete_servers(self):
        for server in self.conn.compute.servers(all_projects=False):
            self.conn.compute.delete_server(server.id)

    def delete_ports(self):
        for network in self.conn.network.networks():
            for port in network.ports(network_id=network.id):
                if port.is_admin_state_up:
                    self.conn.network.update_port(port.id, admin_state_up=False)
                self.conn.network.delete_port(port.id)

    def disable_ports(self):
        for network in self.conn.network.networks():
            for port in network.ports(network_id=network.id):
                if port.is_admin_state_up:
                    self.conn.network.update_port(port.id, admin_state_up=False)


if __name__ == "__main__":
    recover = Recover()
    recover.delete_ports()
    recover.delete_security_group_rules()
    recover.delete_security_groups()
    recover.delete_routers()
    recover.delete_subnets()
    recover.delete_networks()
    recover.delete_servers()
