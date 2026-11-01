import factory
from factory.django import DjangoModelFactory
from apps.workspaces.models import Workspace
from apps.core.enums import WorkspaceStatus


class WorkspaceFactory(DjangoModelFactory):
    class Meta:
        model = Workspace

    subdomain = factory.Sequence(lambda n: f"workspace{n}")
    status = WorkspaceStatus.ACTIVE
    settings_json = factory.LazyAttribute(lambda o: {"display_name": o.subdomain})
