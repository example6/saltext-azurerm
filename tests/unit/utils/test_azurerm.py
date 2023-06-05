from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
import saltext.azurerm.utils.azurerm
from azure.mgmt.resource.resources import ResourceManagementClient

try:
    from salt._logging.impl import SaltLoggingClass
    from salt.exceptions import SaltSystemExit, SaltInvocationError
except ImportError:
    pass


@pytest.fixture()
def credentials():
    class FakeCredential:
        """
        FakeCredential class swiped from the SDK
        """

        def get_token(self, *scopes, **kwargs):  # pylint: disable=unused-argument
            from azure.core.credentials import (  # pylint: disable=import-outside-toplevel
                AccessToken,
            )

            return AccessToken("fake_token", 2527537086)

        def close(self):
            pass

    return FakeCredential()


@pytest.fixture()
def subscription_id():
    return "e6df6af5-9a24-46ff-8527-b55c3788a6dd"


@pytest.fixture()
def cloud_env():
    cloud_env = MagicMock()
    cloud_env.endpoints.resource_manager = "http://localhost/someurl"
    return cloud_env


@pytest.fixture()
def mock_determine_auth(credentials, subscription_id, cloud_env):
    return MagicMock(return_value=(credentials, subscription_id, cloud_env))


def test_log_cloud_error():
    client = "foo"
    message = "bar"

    mock_error = MagicMock()
    mock_info = MagicMock()

    with patch.object(SaltLoggingClass, "info", mock_info), patch.object(
        SaltLoggingClass, "error", mock_error
    ):
        saltext.azurerm.utils.azurerm.log_cloud_error(client, message)
        mock_error.assert_called_once_with(
            "An Azure Resource Manager %s ResourceNotFoundError has occurred: %s", "Foo", "bar"
        )
        saltext.azurerm.utils.azurerm.log_cloud_error(client, message, azurerm_log_level="info")
        mock_info.assert_called_once_with(
            "An Azure Resource Manager %s ResourceNotFoundError has occurred: %s", "Foo", "bar"
        )


@pytest.mark.parametrize(
    "client_type,client_object",
    [
        ("compute", "ComputeManagement"),
        ("authorization", "AuthorizationManagement"),
        ("dns", "DnsManagement"),
        ("storage", "StorageManagement"),
        ("managementlock", "ManagementLock"),
        ("monitor", "MonitorManagement"),
        ("network", "NetworkManagement"),
        ("policy", "Policy"),
        ("privatedns", "PrivateDnsManagement"),
        ("resource", "ResourceManagement"),
        ("subscription", "Subscription"),
        ("web", "WebSiteManagement"),
        ("NOT_THERE", "not_used"),
    ],
)
def test_get_client(client_type, client_object, mock_determine_auth):
    if client_type == "NOT_THERE":
        with pytest.raises(SaltSystemExit):
            saltext.azurerm.utils.azurerm.get_client(client_type)
    else:
        with patch("saltext.azurerm.utils.azurerm._determine_auth", mock_determine_auth):
            client = saltext.azurerm.utils.azurerm.get_client(client_type)
            assert f"{client_object}Client" in str(client)


def test_paged_object_to_list():
    models = ResourceManagementClient.models()

    def _r_groups():
        rg_list = [
            models.ResourceGroup(
                location="eastus",
            ),
            models.ResourceGroup(
                location="westus",
            ),
        ]
        yield from rg_list

    paged_object = _r_groups()

    paged_return = saltext.azurerm.utils.azurerm.paged_object_to_list(paged_object)

    assert isinstance(paged_return, list)
    assert paged_return == [
        {"location": "eastus"},
        {"location": "westus"},
    ]


def test_create_object_model():
    obj = saltext.azurerm.utils.azurerm.create_object_model(
        "network",
        "VirtualNetwork",
    )
    assert "VirtualNetwork" in str(obj.__class__)
    assert obj.as_dict() == {"enable_ddos_protection": False, "enable_vm_protection": False}


def test_compare_list_of_dicts():
    # equal
    old = [
        {"name": "group1", "location": "eastus"},
        {"name": "group2", "location": "eastus"},
    ]
    new = [
        {"name": "group1", "location": "eastus"},
        {"name": "group2", "location": "eastus"},
    ]
    ret = saltext.azurerm.utils.azurerm.compare_list_of_dicts(old, new)
    assert not ret

    # case difference
    new[0]["location"] = "EastUS"
    ret = saltext.azurerm.utils.azurerm.compare_list_of_dicts(old, new)
    assert not ret

    # not equal
    new[0]["location"] = "westus"
    ret = saltext.azurerm.utils.azurerm.compare_list_of_dicts(old, new)
    expected = {
        "changes": {
            "old": old,
            "new": new,
        }
    }
    assert ret == expected

    # missing name key
    new[0].pop("name")
    ret = saltext.azurerm.utils.azurerm.compare_list_of_dicts(old, new)
    expected = {"comment": 'configuration dictionaries must contain the "name" key!'}
    assert ret == expected


def test__determine_auth():
    mock_credentials = MagicMock()
    # test case for service_principal_creds_kwargs and default cloud environment
    with patch("saltext.azurerm.utils.azurerm.ClientSecretCredential", mock_credentials):
        # pylint: disable=protected-access
        _, subscription_id, cloud_env = saltext.azurerm.utils.azurerm._determine_auth(
            subscription_id="54321",
            client_id="12345",
            secret="supersecret",
            tenant="jacktripper",
        )
        assert subscription_id == "54321"
        assert cloud_env.name == "AzureCloud"
        assert mock_credentials.call_args.kwargs["client_id"] == "12345"
        assert mock_credentials.call_args.kwargs["client_secret"] == "supersecret"
        assert mock_credentials.call_args.kwargs["tenant_id"] == "jacktripper"

    mock_credentials.reset_mock()
    # test case for user_pass_creds_kwargs and cloud environment starting with http
    mock_get_cloud_from_metadata_endpoint = MagicMock(return_value=cloud_env)
    with patch("saltext.azurerm.utils.azurerm.UsernamePasswordCredential", mock_credentials), patch(
        "saltext.azurerm.utils.azurerm.get_cloud_from_metadata_endpoint",
        mock_get_cloud_from_metadata_endpoint,
    ):
        # pylint: disable=protected-access
        _, subscription_id, cloud_env = saltext.azurerm.utils.azurerm._determine_auth(
            subscription_id="54321",
            client_id="12345",
            username="user",
            password="password",
            cloud_environment="http://random.com",
        )
        assert subscription_id == "54321"
        assert cloud_env.name == "AzureCloud"
        assert mock_credentials.call_args.kwargs["username"] == "user"
        assert mock_credentials.call_args.kwargs["password"] == "password"
        mock_get_cloud_from_metadata_endpoint.assert_called_once_with("http://random.com")

    mock_credentials.reset_mock()
    # test case for default creds
    with patch("saltext.azurerm.utils.azurerm.DefaultAzureCredential", mock_credentials):
        # pylint: disable=protected-access
        _, subscription_id, cloud_env = saltext.azurerm.utils.azurerm._determine_auth(
            subscription_id="54321",
            cloud_environment="AZURE_US_GOV_CLOUD",
        )
        assert subscription_id == "54321"
        assert cloud_env.name == "AzureUSGovernment"
        assert mock_credentials.call_args.kwargs["cloud_environment"].name == "AzureUSGovernment"

    # no subscription id provided error
    with pytest.raises(SaltInvocationError):
        # pylint: disable=protected-access
        saltext.azurerm.utils.azurerm._determine_auth(
            client_id="12345", secret="supersecret", tenant="jacktripper"
        )
