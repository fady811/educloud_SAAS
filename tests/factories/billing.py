import factory
from factory.django import DjangoModelFactory
from apps.billing.models import Package, Subscription
from apps.core.enums import SubscriptionStatus
from django.utils import timezone
import datetime


class PackageFactory(DjangoModelFactory):
    class Meta:
        model = Package

    name = factory.Sequence(lambda n: f"Package {n}")
    slug = factory.Sequence(lambda n: f"package-{n}")
    price_egp = factory.Faker("pydecimal", left_digits=4, right_digits=2, positive=True)
    duration_months = 1
    max_students = 100
    is_active = True


class SubscriptionFactory(DjangoModelFactory):
    class Meta:
        model = Subscription

    workspace = factory.SubFactory("tests.factories.workspaces.WorkspaceFactory")
    package = factory.SubFactory(PackageFactory)
    status = SubscriptionStatus.ACTIVE
    starts_at = factory.LazyFunction(timezone.now)
    ends_at = factory.LazyFunction(lambda: timezone.now() + datetime.timedelta(days=30))
