from pydantic import Field
import pytest

from middlewared.api.base import (BaseModel, Excluded, excluded_field, ForUpdateMetaclass, single_argument_args,
                                  single_argument_result)
from middlewared.api.base.handler.accept import accept_params
from middlewared.api.base.handler.result import serialize_result
from middlewared.api.v25_04_0.pool_snapshottask import PoolSnapshotTaskCron
from middlewared.service_exception import ValidationErrors


class Object(BaseModel):
    id: int
    name: str
    count: int = 0


class CreateObject(Object):
    id: Excluded = excluded_field()


class UpdateObject(CreateObject, metaclass=ForUpdateMetaclass):
    pass


class UpdateArgs(BaseModel):
    id: int
    data: UpdateObject


@pytest.mark.parametrize("data", [
    {},
    {"name": "Ivan"},
    {"count": 0},
    {"count": 1},
])
def test_for_update(data):
    assert accept_params(UpdateArgs, [1, data]) == [1, data]


def test_single_argument_args():
    @single_argument_args("param")
    class MethodArgs(BaseModel):
        name: str
        count: int = 1

    assert accept_params(MethodArgs, [{"name": "ivan"}]) == [{"name": "ivan", "count": 1}]


def test_single_argument_args_error():
    @single_argument_args("param")
    class MethodArgs(BaseModel):
        name: str
        count: int = 1

    with pytest.raises(ValidationErrors) as ve:
        accept_params(MethodArgs, [{"name": 1}])

    assert ve.value.errors[0].attribute == "param.name"


def test_single_argument_result():
    @single_argument_result
    class MethodResult(BaseModel):
        name: str
        count: int

    assert serialize_result(MethodResult, {"name": "ivan", "count": 1}, True) == {"name": "ivan", "count": 1}


def test_update_with_cron():
    class CreateObjectWithCron(BaseModel):
        schedule: PoolSnapshotTaskCron = Field(default_factory=PoolSnapshotTaskCron)

    class UpdateObjectWithCron(CreateObjectWithCron, metaclass=ForUpdateMetaclass):
        pass

    class UpdateWithCronArgs(BaseModel):
        id: int
        data: UpdateObjectWithCron

    assert accept_params(UpdateWithCronArgs, [1, {}]) == [1, {}]


def test_update_with_alias():
    class CreateObjectWithAlias(BaseModel):
        pass_: str = Field(alias="pass")

    class UpdateObjectWithAlias(CreateObjectWithAlias, metaclass=ForUpdateMetaclass):
        pass

    class UpdateWithAliasArgs(BaseModel):
        id: int
        data: UpdateObjectWithAlias

    assert accept_params(UpdateWithAliasArgs, [1, {"pass": "1"}]) == [1, {"pass": "1"}]
