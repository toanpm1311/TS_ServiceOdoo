from . import models


def _dat_product_post_init(env):
    main_category = env.ref(
        'product.product_category_all', raise_if_not_found=False)
    if main_category:
        main_category.unlink()
    expense_category = env.ref(
        'product.cat_expense', raise_if_not_found=False)
    if expense_category:
        expense_category.unlink()
    saleable_category = env.ref(
        'product.product_category_1', raise_if_not_found=False)
    if saleable_category:
        saleable_category.unlink()
