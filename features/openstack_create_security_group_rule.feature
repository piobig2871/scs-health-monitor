@security_group_rule
@create
Feature: OpenStack Security Group Rule Creation

  Scenario Outline: Connect to OpenStack and create a security group rule
    Given I connect to OpenStack
    Then I should be able to create a security group rule with direction <direction> protocol <protocol> and port range <port_range_min> to <port_range_max>

    Examples: Test security groups rule
    | direction | protocol | port_range_min | port_range_max |
    | ingress   | tcp      | 80             | 80             |
    | egress    | tcp      | 430            | 430            |