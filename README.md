## 迁移前状态：

#### loadbalancer 网络资源：
   1. Neutron DB：
     1. 在 Neutron DB 中会给 vIP 和当前 loadblancer subnet selfip 申请 Neutron Port。
     2. 在 Neutron DB 中会给 loadbalancer subnet 申请多个 Neutron SNAT Port。（SNAT IP 个数取决于配置文的配置）
   2. Bigip:
      1. 会根据 loadbalancer network vlan segmentation ID 创建 vlan/route domain ID。
      2. 会在 vlan 和 route domain 中创建当前 loadbalancer subnet 的 selfip。
      3. 会在 route domain 下创建当前 loadbalancer 的 vIP
      4. 会在当前 route domain 下创建当前 loadbalancer subnet 关联的 SNAT IP（SNAT IP 个数取决于配置文的配置）。

#### Member 网络资源：
   1. Neutron DB：
      1. 在 Neutron DB 中给 Member IP 和 当前 member subnet selfip 申请 Neutron Port。
      2. 在 Neutron DB 中给 Member subnet 申请多个 Neutron SNAT Port（SNAT IP 个数取决于配置文的配置）.
      3. 如果 loadbalancer 和 member 同 network 和 subnet，就不会重复以上 1，2 申请过程。
   2. BigIP：
      1. 会根据 Member network vlan segmentation ID 创建 vlan/route domain ID。
      2. 会在 vlan 和 route domain 中创建当前 Member subnet 的 selfip。
      3. 会在 route domain 下创建 member node 和服务 IP Port
      4. 会在当前 route domain 下创建当前 Member subnet 关联的 SNAT IP。（SNAT IP 个数取决于配置文的配置）


## 迁移后状态：

#### Loadbalancer 网络资源：
   1. Neutron DB：
      1. 在 Neutron DB 中会给 vIP 和当前 loadblancer network 下关联的 subnet 申请 Neutron selfip port。
      2. 在 Neutron DB 中会给 loadbalancer network 下关联的 subnet 申请 Neutron SNAT port，一个 SNAT port 关联多个 IP， IP 个数由 flavor 大小决定。
   2. BigIP：
      1. 会根据 loadbalancer network vlan segmentation ID 创建 vlan/route domain ID。 
      2. 会在 vlan 和 route domain 中创建当前 loadbalancer network 关联的所有 subnet 的 selfip。
      3. 会在 vlan 和 route domain 中创建当前 loadbalancer network 关联的所有 subnet 的 default route。
      4. 会在 route domain 下创建当前 loadbalancer 的 vIP
      5. 会在当前 route domain 下创建当前 loadbalancer network 关联的所有 subnet 关联的 SNAT IP, IP 个数由 flavor 大小决定。

#### Member 网络资源：
   1. Neutron DB:
      1. 在 Neutron DB 中给 Member IP 申请 Neutron Port。 
   2. BigIP:
      1. 会在 **Loadbalancer route domain** 下创建 member node IP 和 member 服务 IP Port。

### 迁移注意事项：

1. 此迁移必须在 SNAT IP 和 selfip 迁移完成后运行
2. 迁移中有任何异常，需要回复备份配置重新迁移。
3. <font color="red">！！！ 迁移正确完成后，admin 用户一定要在 bigip 上执行 `tmsh save /sys config partitions all`</font>

### 运行命令：

```
sudo python main.py --config-file /etc/neutron/services/f5/f5-openstack-agent.ini --config-file /etc/neutron/neutron.conf --host-ip 10.145.71.57 --f5-agent 7c6a4b8e-7d9a-40fe-b55e-c3516d24f3e9 --dry-run

--config-file /etc/neutron/neutron.conf: 当前 neutron 配置文件。
--config-file /etc/neutron/service/f5/f5-openstack-agent.ini: 当前 F5 agent provider 配置文件。
--f5-agent 7c6a4b8e-7d9a-40fe-b55e-c3516d24f3e9: 当前 F5 agent ID。
--host-ip 10.145.71.57: 当前 F5 agent provider 控制的其中一台 bigip host 地址，如果有多台，需要多次运行这个命令。
--dry-run: 用于数据构建测试，注意此测试不会真正下发任何配置，不会对 Neutron DB 和 F5 BigIP 设备做任何更改。
```

### route 迁移图示 和 迁移步骤：

![L3_migration.jpg](https://s2.loli.net/2022/06/10/7kPrvlEciXKQHZR.jpg)

具体 SNAT IP 迁移部分可以参考：https://gitswarm.f5net.com/openstack/snat-migration  


#### ！！！ 迁移正确完成后，admin 用户一定要在 bigip 上执行 tmsh save /sys config partitions all
