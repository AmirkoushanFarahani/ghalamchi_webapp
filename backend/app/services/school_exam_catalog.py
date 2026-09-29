"""Default exam and book-voucher catalog imported from Book1.xlsx."""

from decimal import Decimal

ExamPrice = tuple[int, int, int]
CatalogRow = tuple[str, str | None, int, int, tuple[ExamPrice, ExamPrice, ExamPrice]]

# grade, academic track, book voucher, book discount, and the three selectable plans.
# Each plan is (exam count, unit price, total price), in rials.
DEFAULT_EXAM_CATALOG: tuple[CatalogRow, ...] = (
    *(
        (
            "GRADE_12",
            track,
            4_000_000,
            500_000,
            ((27, 460_000, 12_420_000), (27, 550_000, 14_850_000), (28, 600_000, 16_800_000)),
        )
        for track in ("MATHEMATICS_PHYSICS", "EXPERIMENTAL", "HUMANITIES", "RELIGIOUS_STUDIES")
    ),
    *(
        (
            "GRADE_12",
            track,
            2_000_000,
            200_000,
            ((27, 460_000, 12_420_000), (27, 550_000, 14_850_000), (28, 600_000, 16_800_000)),
        )
        for track in ("ART", "LANGUAGES")
    ),
    *(
        (
            "GRADE_12",
            track,
            2_000_000,
            200_000,
            ((26, 420_000, 10_920_000), (26, 490_000, 12_740_000), (27, 550_000, 14_850_000)),
        )
        for track in (
            "ELECTROTECHNICS",
            "PHYSICAL_EDUCATION",
            "ACCOUNTING",
            "COMPUTER_NETWORK_SOFTWARE",
            "AUTOMOTIVE_MECHANICS",
        )
    ),
    *(
        (
            "GRADE_11",
            track,
            2_000_000,
            200_000,
            ((26, 420_000, 10_920_000), (26, 490_000, 12_740_000), (27, 550_000, 14_850_000)),
        )
        for track in (
            "ELECTROTECHNICS",
            "PHYSICAL_EDUCATION",
            "ACCOUNTING",
            "COMPUTER_NETWORK_SOFTWARE",
            "AUTOMOTIVE_MECHANICS",
        )
    ),
    *(
        (
            "GRADE_11",
            track,
            3_000_000,
            300_000,
            ((26, 420_000, 10_920_000), (26, 490_000, 12_740_000), (27, 550_000, 14_850_000)),
        )
        for track in ("EXPERIMENTAL", "MATHEMATICS_PHYSICS", "HUMANITIES", "RELIGIOUS_STUDIES")
    ),
    *(
        (
            "GRADE_10",
            track,
            3_000_000,
            300_000,
            ((26, 420_000, 10_920_000), (26, 490_000, 12_740_000), (27, 550_000, 14_850_000)),
        )
        for track in ("EXPERIMENTAL", "MATHEMATICS_PHYSICS", "HUMANITIES", "RELIGIOUS_STUDIES")
    ),
    *(
        (
            "GRADE_10",
            track,
            2_000_000,
            300_000,
            ((26, 420_000, 10_920_000), (26, 490_000, 12_740_000), (27, 550_000, 14_850_000)),
        )
        for track in (
            "ELECTROTECHNICS",
            "PHYSICAL_EDUCATION",
            "ACCOUNTING",
            "COMPUTER_NETWORK_SOFTWARE",
            "AUTOMOTIVE_MECHANICS",
        )
    ),
    (
        "GRADE_9",
        None,
        2_000_000,
        300_000,
        ((26, 400_000, 10_400_000), (27, 490_000, 13_230_000), (28, 550_000, 15_400_000)),
    ),
    *(
        (
            grade,
            None,
            2_000_000,
            300_000,
            ((26, 400_000, 10_400_000), (26, 480_000, 12_480_000), (27, 540_000, 14_580_000)),
        )
        for grade in ("GRADE_8", "GRADE_7")
    ),
    (
        "GRADE_6",
        None,
        2_000_000,
        300_000,
        ((26, 380_000, 9_880_000), (27, 490_000, 13_230_000), (28, 540_000, 15_120_000)),
    ),
    *(
        (
            grade,
            None,
            2_000_000,
            300_000,
            ((26, 380_000, 9_880_000), (26, 460_000, 11_960_000), (27, 500_000, 13_500_000)),
        )
        for grade in ("GRADE_5", "GRADE_4", "GRADE_3", "GRADE_2")
    ),
)

PLAN_CODES = ("0215", "00231", "0331")


def decimal(value: int) -> Decimal:
    return Decimal(value)
