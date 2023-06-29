"""
Azure Resource Manager Compute Execution Module

.. versionadded:: 2019.2.0

:maintainer: <devops@eitr.tech>
:maturity: new
:platform: linux

:configuration: This module requires Azure Resource Manager credentials to be passed as keyword arguments
    to every function in order to work properly.

    Required provider parameters:

    if using username and password:
      * ``subscription_id``
      * ``username``
      * ``password``

    if using a service principal:
      * ``subscription_id``
      * ``tenant``
      * ``client_id``
      * ``secret``

    Optional provider parameters:

**cloud_environment**: Used to point the cloud driver to different API endpoints, such as Azure GovCloud.
    Possible values:
      * ``AZURE_PUBLIC_CLOUD`` (default)
      * ``AZURE_CHINA_CLOUD``
      * ``AZURE_US_GOV_CLOUD``
      * ``AZURE_GERMAN_CLOUD``

"""
# Python libs
import logging

import saltext.azurerm.utils.azurerm

# Azure libs
HAS_LIBS = False
try:
    import azure.mgmt.compute.models  # pylint: disable=unused-import
    from azure.core.exceptions import ResourceNotFoundError, SerializationError, HttpResponseError

    HAS_LIBS = True
except ImportError:
    pass

__virtualname__ = "azurerm_compute"

log = logging.getLogger(__name__)


def __virtual__():
    if not HAS_LIBS:
        return (
            False,
            "The following dependencies are required to use the Azure Resource Manager modules: "
            "Microsoft Azure SDK for Python >= 2.0rc6, "
            "MS REST Azure (msrestazure) >= 0.4",
        )

    return __virtualname__


def availability_set_create_or_update(
    name, resource_group, **kwargs
):  # pylint: disable=invalid-name
    """
    .. versionadded:: 2019.2.0

    Create or update an availability set.

    :param name: The availability set to create.

    :param resource_group: The resource group name assigned to the
        availability set.

    CLI Example:

    .. code-block:: bash

        salt-call azurerm_compute.availability_set_create_or_update testset testgroup

    """
    if "location" not in kwargs:
        rg_props = __salt__["azurerm_resource.resource_group_get"](resource_group, **kwargs)

        if "error" in rg_props:
            log.error("Unable to determine location from resource group specified.")
            return False
        kwargs["location"] = rg_props["location"]

    compconn = saltext.azurerm.utils.azurerm.get_client("compute", **kwargs)

    # Use VM names to link to the IDs of existing VMs.
    if isinstance(kwargs.get("virtual_machines"), list):
        vm_list = []
        for vm_name in kwargs.get("virtual_machines"):
            vm_instance = __salt__["azurerm_compute.virtual_machine_get"](
                name=vm_name, resource_group=resource_group, **kwargs
            )
            if "error" not in vm_instance:
                vm_list.append({"id": str(vm_instance["id"])})
        kwargs["virtual_machines"] = vm_list

    try:
        setmodel = saltext.azurerm.utils.azurerm.create_object_model(
            "compute", "AvailabilitySet", **kwargs
        )
    except TypeError as exc:
        result = {"error": "The object model could not be built. ({})".format(str(exc))}
        return result

    try:
        av_set = compconn.availability_sets.create_or_update(
            resource_group_name=resource_group,
            availability_set_name=name,
            parameters=setmodel,
        )
        result = av_set.as_dict()

    except HttpResponseError as exc:
        saltext.azurerm.utils.azurerm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}
    except SerializationError as exc:
        result = {"error": "The object model could not be parsed. ({})".format(str(exc))}

    return result


def availability_set_delete(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Delete an availability set.

    :param name: The availability set to delete.

    :param resource_group: The resource group name assigned to the
        availability set.

    CLI Example:

    .. code-block:: bash

        salt-call azurerm_compute.availability_set_delete testset testgroup

    """
    result = False
    compconn = saltext.azurerm.utils.azurerm.get_client("compute", **kwargs)
    try:
        compconn.availability_sets.delete(
            resource_group_name=resource_group, availability_set_name=name
        )
        result = True

    except HttpResponseError as exc:
        saltext.azurerm.utils.azurerm.log_cloud_error("compute", str(exc), **kwargs)

    return result


def availability_set_get(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Get a dictionary representing an availability set's properties.

    :param name: The availability set to get.

    :param resource_group: The resource group name assigned to the
        availability set.

    CLI Example:

    .. code-block:: bash

        salt-call azurerm_compute.availability_set_get testset testgroup

    """
    compconn = saltext.azurerm.utils.azurerm.get_client("compute", **kwargs)
    try:
        av_set = compconn.availability_sets.get(
            resource_group_name=resource_group, availability_set_name=name
        )
        result = av_set.as_dict()

    except (ResourceNotFoundError, HttpResponseError) as exc:
        saltext.azurerm.utils.azurerm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def availability_sets_list(resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    List all availability sets within a resource group.

    :param resource_group: The resource group name to list availability
        sets within.

    CLI Example:

    .. code-block:: bash

        salt-call azurerm_compute.availability_sets_list testgroup

    """
    result = {}
    compconn = saltext.azurerm.utils.azurerm.get_client("compute", **kwargs)
    try:
        avail_sets = saltext.azurerm.utils.azurerm.paged_object_to_list(
            compconn.availability_sets.list(resource_group_name=resource_group)
        )

        for avail_set in avail_sets:
            result[avail_set["name"]] = avail_set
    except HttpResponseError as exc:
        saltext.azurerm.utils.azurerm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def availability_sets_list_available_sizes(
    name, resource_group, **kwargs
):  # pylint: disable=invalid-name
    """
    .. versionadded:: 2019.2.0

    List all available virtual machine sizes that can be used to
    to create a new virtual machine in an existing availability set.

    :param name: The availability set name to list available
        virtual machine sizes within.

    :param resource_group: The resource group name to list available
        availability set sizes within.

    CLI Example:

    .. code-block:: bash

        salt-call azurerm_compute.availability_sets_list_available_sizes testset testgroup

    """
    result = {}
    compconn = saltext.azurerm.utils.azurerm.get_client("compute", **kwargs)
    try:
        sizes = saltext.azurerm.utils.azurerm.paged_object_to_list(
            compconn.availability_sets.list_available_sizes(
                resource_group_name=resource_group, availability_set_name=name
            )
        )

        for size in sizes:
            result[size["name"]] = size
    except (ResourceNotFoundError, HttpResponseError) as exc:
        saltext.azurerm.utils.azurerm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machine_capture(
    name, destination_name, resource_group, prefix="capture-", overwrite=False, **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Captures the VM by copying virtual hard disks of the VM and outputs
    a template that can be used to create similar VMs.

    :param name: The name of the virtual machine.

    :param destination_name: The destination container name.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    :param prefix: (Default: 'capture-') The captured virtual hard disk's name prefix.

    :param overwrite: (Default: False) Overwrite the destination disk in case of conflict.

    CLI Example:

    .. code-block:: bash

        salt-call azurerm_compute.virtual_machine_capture testvm testcontainer testgroup

    """
    # pylint: disable=invalid-name
    VirtualMachineCaptureParameters = getattr(
        azure.mgmt.compute.models, "VirtualMachineCaptureParameters"
    )

    compconn = saltext.azurerm.utils.azurerm.get_client("compute", **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.begin_capture(
            resource_group_name=resource_group,
            vm_name=name,
            parameters=VirtualMachineCaptureParameters(
                vhd_prefix=prefix,
                destination_container_name=destination_name,
                overwrite_vhds=overwrite,
            ),
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except HttpResponseError as exc:
        saltext.azurerm.utils.azurerm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machine_get(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Retrieves information about the model view or the instance view of a
    virtual machine.

    :param name: The name of the virtual machine.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurerm_compute.virtual_machine_get testvm testgroup

    """
    expand = kwargs.get("expand")

    compconn = saltext.azurerm.utils.azurerm.get_client("compute", **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.get(
            resource_group_name=resource_group, vm_name=name, expand=expand
        )
        result = vm.as_dict()
    except HttpResponseError as exc:
        saltext.azurerm.utils.azurerm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machine_convert_to_managed_disks(
    name, resource_group, **kwargs
):  # pylint: disable=invalid-name
    """
    .. versionadded:: 2019.2.0

    Converts virtual machine disks from blob-based to managed disks. Virtual
    machine must be stop-deallocated before invoking this operation.

    :param name: The name of the virtual machine to convert.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurerm_compute.virtual_machine_convert_to_managed_disks testvm testgroup

    """
    compconn = saltext.azurerm.utils.azurerm.get_client("compute", **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.begin_convert_to_managed_disks(
            resource_group_name=resource_group, vm_name=name
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except HttpResponseError as exc:
        saltext.azurerm.utils.azurerm.log_cloud_error("comput", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machine_deallocate(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Power off a virtual machine and deallocate compute resources.

    :param name: The name of the virtual machine to deallocate.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurerm_compute.virtual_machine_deallocate testvm testgroup

    """
    compconn = saltext.azurerm.utils.azurerm.get_client("compute", **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.begin_deallocate(
            resource_group_name=resource_group, vm_name=name
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except HttpResponseError as exc:
        saltext.azurerm.utils.azurerm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machine_generalize(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Set the state of a virtual machine to 'generalized'.

    :param name: The name of the virtual machine.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurerm_compute.virtual_machine_generalize testvm testgroup

    """
    result = False
    compconn = saltext.azurerm.utils.azurerm.get_client("compute", **kwargs)
    try:
        compconn.virtual_machines.generalize(resource_group_name=resource_group, vm_name=name)
        result = True
    except HttpResponseError as exc:
        saltext.azurerm.utils.azurerm.log_cloud_error("compute", str(exc), **kwargs)

    return result


def virtual_machines_list(resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    List all virtual machines within a resource group.

    :param resource_group: The resource group name to list virtual
        machines within.

    CLI Example:

    .. code-block:: bash

        salt-call azurerm_compute.virtual_machines_list testgroup

    """
    result = {}
    compconn = saltext.azurerm.utils.azurerm.get_client("compute", **kwargs)
    try:
        vms = saltext.azurerm.utils.azurerm.paged_object_to_list(
            compconn.virtual_machines.list(resource_group_name=resource_group)
        )
        for vm in vms:  # pylint: disable=invalid-name
            result[vm["name"]] = vm
    except HttpResponseError as exc:
        saltext.azurerm.utils.azurerm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machines_list_all(**kwargs):
    """
    .. versionadded:: 2019.2.0

    List all virtual machines within a subscription.

    CLI Example:

    .. code-block:: bash

        salt-call azurerm_compute.virtual_machines_list_all

    """
    result = {}
    compconn = saltext.azurerm.utils.azurerm.get_client("compute", **kwargs)
    try:
        vms = saltext.azurerm.utils.azurerm.paged_object_to_list(
            compconn.virtual_machines.list_all()
        )
        for vm in vms:  # pylint: disable=invalid-name
            result[vm["name"]] = vm
    except HttpResponseError as exc:
        saltext.azurerm.utils.azurerm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machines_list_available_sizes(
    name, resource_group, **kwargs
):  # pylint: disable=invalid-name
    """
    .. versionadded:: 2019.2.0

    Lists all available virtual machine sizes to which the specified virtual
    machine can be resized.

    :param name: The name of the virtual machine.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurerm_compute.virtual_machines_list_available_sizes testvm testgroup

    """
    result = {}
    compconn = saltext.azurerm.utils.azurerm.get_client("compute", **kwargs)
    try:
        sizes = saltext.azurerm.utils.azurerm.paged_object_to_list(
            compconn.virtual_machines.list_available_sizes(
                resource_group_name=resource_group, vm_name=name
            )
        )
        for size in sizes:
            result[size["name"]] = size
    except HttpResponseError as exc:
        saltext.azurerm.utils.azurerm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machine_power_off(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Power off (stop) a virtual machine.

    :param name: The name of the virtual machine to stop.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurerm_compute.virtual_machine_power_off testvm testgroup

    """
    compconn = saltext.azurerm.utils.azurerm.get_client("compute", **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.begin_power_off(
            resource_group_name=resource_group, vm_name=name
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except HttpResponseError as exc:
        saltext.azurerm.utils.azurerm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machine_restart(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Restart a virtual machine.

    :param name: The name of the virtual machine to restart.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurerm_compute.virtual_machine_restart testvm testgroup

    """
    compconn = saltext.azurerm.utils.azurerm.get_client("compute", **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.begin_restart(
            resource_group_name=resource_group, vm_name=name
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except HttpResponseError as exc:
        saltext.azurerm.utils.azurerm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machine_start(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Power on (start) a virtual machine.

    :param name: The name of the virtual machine to start.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurerm_compute.virtual_machine_start testvm testgroup

    """
    compconn = saltext.azurerm.utils.azurerm.get_client("compute", **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.begin_start(resource_group_name=resource_group, vm_name=name)
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except HttpResponseError as exc:
        saltext.azurerm.utils.azurerm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machine_redeploy(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Redeploy a virtual machine.

    :param name: The name of the virtual machine to redeploy.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurerm_compute.virtual_machine_redeploy testvm testgroup

    """
    compconn = saltext.azurerm.utils.azurerm.get_client("compute", **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.begin_redeploy(
            resource_group_name=resource_group, vm_name=name
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except HttpResponseError as exc:
        saltext.azurerm.utils.azurerm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result
