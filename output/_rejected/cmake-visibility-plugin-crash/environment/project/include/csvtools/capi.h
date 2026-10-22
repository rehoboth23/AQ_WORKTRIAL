#ifndef CSVTOOLS_CAPI_H
#define CSVTOOLS_CAPI_H

#ifdef __cplusplus
extern "C" {
#endif

__attribute__((visibility("default"))) void csvtools_process(const char* filename);
__attribute__((visibility("default"))) void csvtools_add_plugin_path(const char* path);

#ifdef __cplusplus
}
#endif

#endif
