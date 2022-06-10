# -*- coding: utf-8 -*-

import queries
import options
import netaddr
from pprint import pprint
from oslo_config import cfg

from f5.bigip import ManagementRoot
import resource_helper
import urllib

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from os_client import neutron_client

options.load_options()
options.parse_options()
conf = cfg.CONF

# agent_id = "e38c87fa-c190-409b-87ab-c54b3a53dbcf"
# host_ip = "10.145.72.33"
agent_id = conf.f5_agent
host_ip = conf.host_ip
db_query = queries.Queries()

if conf.environment_prefix:
    partition_prefix = conf.environment_prefix + '_'
else:
    raise Exception("Cannot found partition prefix")

def get_device_name(host, device_list):
    if not device_list:
        return
    for device in device_list:
        if host == device.managementIp:
            return device.name

def init_bigip(host, user, passwd):
    bigip = ManagementRoot(host, user, passwd)
    devices = bigip.tm.cm.devices.get_collection()
    device_name = get_device_name(host, devices)
    if not device_name:
        raise Exception("Cannot found device name for host %s" % host)
    bigip.device_name = device_name
    return bigip

def resource_tree(agent_id):
    tree = dict()
    tenant_map = tree[agent_id] = dict()
    loadbalancers = db_query.get_loadbalancers_by_agent_id(agent_id)

    for lb in loadbalancers:
        if lb.project_id not in tenant_map:
            tenant_map[lb.project_id] = list()
        lb.subnet = db_query.get_subnet(lb.subnet_id)
        tenant_map[lb.project_id] += [lb]

        pools = db_query.get_pools_by_lb_id(lb.id)
        lb.pools = pools
        # pprint(lb.__dict__)
    return tree

def partition_name(tenant_id):
    if tenant_id is not None:
        name = partition_prefix + tenant_id
    else:
        name = "Common"
    return name

def get_pool_name(pool):
    return partition_prefix + pool.id

def get_member_name(mb, rd):
    if '%' in mb.address:
        ip = mb.address.split('%')[0]
        ip_version = netaddr.IPAddress(ip)
        if ip_version.version == 4:
            port = mb.name.split(':')[-1]
            return  ip + '%' + str(rd) + ':' + port
        if ip_version.version == 6:
            port = mb.name.split('.')[-1]
            return  ip + '%' + str(rd) + '.' + port
    return  mb.name

def get_member_addr(mb, rd):
    ip = mb.address.split('%')[0]
    return ip + '%' + str(rd)

def get_pool(bigip, partition, name):
    pool_helper = resource_helper.BigIPResourceHelper(resource_helper.ResourceType.pool)
    pool = pool_helper.load(bigip, partition=partition, name=name, expand_subcollections=True)
    return pool

def clean_nodes(bigip, parition, nodes):
    node_helper = resource_helper.BigIPResourceHelper(resource_helper.ResourceType.node)
    for nd in nodes:
        try:
            node_helper.delete(bigip, partition=partition, name=urllib.quote(nd))
        except Exception as exc:
            if 400 == exc.response.status_code:
                if "is referenced by a member of pool" not in exc.response.text:
                   raise exc
            else:
               raise exc

def create_route(bigip, payload):
    route_helper = resource_helper.BigIPResourceHelper(resource_helper.ResourceType.route)
    try:
        route_helper.create(bigip, payload)
    except Exception as exc:
        if 409 == exc.response.status_code:
            if "already exists in partition" not in exc.response.text:
                raise exc
        else:
            raise exc

def get_selfip_name(bigip, subnet_id):
    return "local-" + bigip.device_name  + "-" + subnet_id

def get_selfip(bigip, partition, selfip_name):
    selfip_helper = resource_helper.BigIPResourceHelper(resource_helper.ResourceType.selfip)
    result = None
    try:
        result = selfip_helper.load(bigip, partition=partition, name=selfip_name)
    except Exception as exc:
        if 404 == exc.response.status_code:
            pass
        else:
            raise exc
    return result



def get_lb_seg_num(lb):
    segs = len(lb.subnet.network.segments)
    if segs > 1:
        for seg in segs:
            if seg.network_type == "vlan":
                segementation = seg.segmentation_id
    elif segs == 1:
        net_type = lb.subnet.network.segments[0].network_type
        if net_type != "vlan":
            raise Exception("Can not find vlan segmentation id of network %s\n" % lb.subnet.network.__dict__)
        segementation = lb.subnet.network.segments[0].segmentation_id
    else:
        raise Exception("Can not get network segements from DB\n")

    return segementation

def get_gateway_ip(subnet, seg_num):
    return subnet.gateway_ip + '%' + str(seg_num)

def get_route_name(subnet, seg_num):
    if subnet.ip_version == 4:
        return 'IPv4_default_route_' + str(seg_num)
    elif subnet.ip_version == 6:
        return 'IPv6_default_route_' + str(seg_num)
    else:
        raise Exception(
            "Can not get route name "
            "for subent %s\n" % subnet.__dict__
        )

def default_route_dst(subnet, seg_num):
    if subnet.ip_version == 4:
        return '0.0.0.0' + "%" + str(seg_num) + '/0'
    elif subnet.ip_version == 6:
        return '::' + "%" + str(seg_num) + '/0'
    else:
        raise Exception(
            "Can not get default route destination "
            "for subent %s\n" % subnet.__dict__
        )

def get_partition_vlan(vlan_info):
    info = vlan_info.split('/')

    if len(info) != 3:
        raise Exception("Can not get vlan from info %s to delete" % info)
    partition = info[1]
    vlan_name = info[2]

    return partition, vlan_name

def delete_vlan(bigip, vlan_info, DRYRUN=True):

    partition, vlan_name = get_partition_vlan(vlan_info)
    vlan_helper = resource_helper.BigIPResourceHelper(resource_helper.ResourceType.vlan)

    try:
        print ("Delete vlan %s in partition %s on bigip %s" % (vlan_name, partition, bigip.hostname))
        if not DRYRUN:
            vlan_helper.delete(bigip, partition=partition, name=vlan_name)
    except Exception as exc:
        if 404 == exc.response.status_code:
            pass
        elif 400 == exc.response.status_code:
            if "cannot be deleted because it is in use by a self IP" not in exc.response.text:
                raise exc
        else:
           raise exc

def delete_rd(bigip, subnet_id, partition, DRYRUN=True):
    subnet = db_query.get_subnet(subnet_id)
    rd_name = partition_prefix + subnet.network_id

    rd_helper = resource_helper.BigIPResourceHelper(resource_helper.ResourceType.route_domain)
    try:
        print ("Delete route domain %s in partition %s on bigip %s\n" % (rd_name, partition, bigip.hostname))
        if not DRYRUN:
            rd_helper.delete(bigip, partition=partition, name=rd_name)
    except Exception as exc:
        if 404 == exc.response.status_code:
            pass
        elif 400 == exc.response.status_code:
            if "is referenced by" not in exc.response.text:
                raise exc
        else:
           raise exc

DRYRUN=conf.dry_run
bigip = init_bigip(host_ip, conf.icontrol_username, conf.icontrol_password)
resource = resource_tree(agent_id)
# pprint(resource)

# delete rebuild members
# 1. delete old members
# 2. update pool rebuild new members
# 3. clean all the old nodes
for tenant_res in resource.values():
    for tenant_id, lbs in tenant_res.items():

        partition = partition_name(tenant_id)
        partition_mb_subnets = set()
        partition_lb_subnets = set()

        print("\n==============================================")
        print("Start operations for Partition %s\n" % partition)

        for lb in lbs:
            seg_id = None
            seg_id = get_lb_seg_num(lb)
            # print seg_id
            if seg_id == None:
                raise Exception("Can not find segmentation id of nework %s\n" % lb.subnet.network.__dict__)

            # rebuild pool member, and clean nodes for each lb
            # member use lb vlan/route domain
            pools = lb.pools
            for pl in pools:
                # 1. delete old members for the pool
                # 2. update pool rebuild new members
                # 3. clean all the old nodes
                new_members = list()
                old_nodes = set()

                pl_name = get_pool_name(pl)
                pool = get_pool(bigip, partition, pl_name)
                members = pool.members_s.get_collection()

                for mb in members:
                    new_mb = dict()
                    if mb.attrs.get("ratio"):
                        new_mb['ratio'] = mb.ratio
                    if mb.attrs.get("description"):
                        new_mb['description'] = mb.description
                    new_mb['partition'] = mb.partition
                    new_mb['name'] = get_member_name(mb, seg_id)
                    new_mb['address'] = get_member_addr(mb, seg_id)

                    old_nodes |= {mb.address}
                    print ("deleting old member: ")
                    pprint(mb.attrs)
                    print("\n")
                    if not DRYRUN:
                        mb.delete()

                    new_members.append(new_mb)

                if new_members:
                    # print("modify pool: ")
                    # pprint(pool.attrs)
                    # print("\n")
                    print("rebuild members: ")
                    pprint(new_members)
                    print("\n")
                    if not DRYRUN:
                        resp = pool.modify(**{'members': new_members})
                if old_nodes:
                    print("Try to clean nodes: ")
                    pprint(old_nodes)
                    print("\n")
                    if not DRYRUN:
                        clean_nodes(bigip, partition, old_nodes)

                # selfips nedd to delete
                # 1. check subnet selfip to delete for the pool
                for lbaas_mb in pl.members:
                    partition_mb_subnets |= {lbaas_mb.subnet_id}

            # assume selfip has been created by snat migration
            # the we create route for each lb
            # gateway use lb vlan/route domain
            net_id = lb.subnet.network_id
            subnets = db_query.get_subnets_by_network_id(net_id)
            assert 0 < len(subnets) <=2 , "Subnets number of network %s is not corrects" % net_id
            for subnet in subnets:
                # selfip_name = get_selfip_name(bigip, subnet_id)
                # check_and_create_selfip(subnet)
                route_name = get_route_name(subnet, seg_id)
                gateway_ip = get_gateway_ip(subnet, seg_id)
                dst = default_route_dst(subnet, seg_id)
                payload = {
                    "name": route_name,
                    "partition": partition,
                    "gw": gateway_ip,
                    "network": dst,
                }
                print("Build default gateway routes for partition %s" % partition)
                pprint(payload)
                print("\n")
                if not DRYRUN:
                    create_route(bigip, payload)

                # selfips need to keep
                # get selfip for comparing with members selfip
                partition_lb_subnets |= {subnet.id}

            # create route for this partition

        # delete selfip/vlan/route domain
        # member selfip - lb seflip, delete the different selfip and route, vlan
        print ("Loadbalancer subnets %s" % partition_lb_subnets)
        print ("Member subnets %s" % partition_mb_subnets)
        print("\n")
        subnets_check_list = partition_mb_subnets - partition_lb_subnets
        print ("Subnets (vlan/route domain/selfip) check list for partition %s" % partition)
        pprint(subnets_check_list)
        print("\n")
        if subnets_check_list:
            for subnet_id in subnets_check_list:
                selfip_name = get_selfip_name(bigip, subnet_id)
                selfip_port = None

                try:
                     selfip_port = neutron_client.find_resource('port', selfip_name)
                except Exception as exc:
                    print("Selfip neutron port %s not found" % selfip_name)
                if selfip_port:
                    print("Deleting selfip neutron port %s" % selfip_name)
                    if not DRYRUN:
                        try:
                            neutron_client.delete_port(selfip_port['id'])
                        except Exception as exc:
                            if 404 == exc.status_code:
                                if "could not be found" not in exc.message:
                                    raise exc
                            else:
                                raise exc

                selfip = get_selfip(bigip, partition, selfip_name)
                
                if selfip:
                    vlan = selfip.vlan

                    print("Deleting selfip %s on bigip %s " % (selfip_name, bigip.hostname))
                    if not DRYRUN:
                        try:
                            selfip.delete()
                        except Exception as exc:
                            if 400 == exc.response.status_code:
                                if "because it would leave a route unreachable." not in exc.response.text:
                                    raise exc
                            elif 404 == exc.response.status_code:
                                pass
                            else:
                                raise exc

                    delete_vlan(bigip, vlan, DRYRUN)
                    delete_rd(bigip, subnet_id, partition, DRYRUN)
                else:
                    print("Selfip %s not found in partition %s on Bigip %s" % (selfip_name, partition, bigip.hostname))

        print("Finish operations for Partition %s" % partition)
        print("==============================================\n")
