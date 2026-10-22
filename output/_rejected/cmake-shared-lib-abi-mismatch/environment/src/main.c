#include <stdio.h>
#include "types.h"
#include "render.h"

int main(void) {
    Vec3 normal = {1.0, 0.0, 0.0};
    Vec3 light_dir = {1.0, 1.0, 1.0};
    scalar_t diffuse = compute_diffuse(&normal, &light_dir);

    Vec3 v0 = {0.0, 0.0, 0.0};
    Vec3 v1 = {1.0, 0.0, 0.0};
    Vec3 v2 = {0.0, 1.0, 0.0};
    scalar_t area = compute_triangle_area(&v0, &v1, &v2);

    printf("Diffuse: %.6f\n", diffuse);
    printf("Area: %.6f\n", area);

    int passed = 1;

    if (!(diffuse > 0.577 && diffuse < 0.578)) {
        passed = 0;
    }

    if (!(area > 0.499 && area < 0.501)) {
        passed = 0;
    }

    if (passed) {
        printf("ALL TESTS PASSED\n");
        return 0;
    } else {
        printf("TESTS FAILED\n");
        return 1;
    }
}
