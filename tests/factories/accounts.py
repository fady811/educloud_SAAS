import factory
from factory.django import DjangoModelFactory
from apps.accounts.models import User
from apps.workspaces.models import WorkspaceMembership
from apps.core.enums import Role


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    full_name = factory.Faker("name")
    is_active = True
    password = factory.PostGenerationMethodCall("set_password", "testpass123")


class WorkspaceMembershipFactory(DjangoModelFactory):
    class Meta:
        model = WorkspaceMembership

    user = factory.SubFactory(UserFactory)
    workspace = factory.SubFactory("tests.factories.workspaces.WorkspaceFactory")
    role = Role.STUDENT
    is_owner = False
