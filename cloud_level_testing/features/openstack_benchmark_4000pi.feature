@vm
@benchmark
Feature: Test VM under load

  Scenario Outline: Test VM response time while under load (calculating 4000 digits of pi)
    Given I can get the shared context from previous feature
    Given I have deployed JHs
    And I have a private key at <keypair_name> for <username>
    Then I should be able to retrieve the first floating ip and portnumber of the network
    Then I should be able to SSH into the VM
    Then I start calculating 4000 digits of pi on VM and check the ping response

  Examples:
    |keypair_name | username |
    |infra-keypair|  ubuntu  |