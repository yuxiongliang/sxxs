"""平台级业务类目：决定「租户归到哪一类」与「平台向该租户抽多少佣」。

注意与商品类目（app/models/catalog.py 的 Category）区分：

* Category         —— 租户自己的商品分类，租户维度，用于站内橱窗；
* ServiceCategory  —— 平台的经营类目，平台维度，决定抽佣比例（万分比）。

commission_bps 用万分比：500 = 5%，10000 = 100%。买断套餐的租户按 0 处理，
那是套餐侧的性质，不写回类目本身（同一个类目里既有买断租户也有抽佣租户）。
"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ServiceCategory(Base, TimestampMixin):
    __tablename__ = "service_categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 稳定的机器标识，改名不改 code
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(255), default="")
    # 抽佣比例（万分比）：500 = 5%
    commission_bps: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)
