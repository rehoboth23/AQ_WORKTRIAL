#ifndef CSVTOOLS_EXPORT_H
#define CSVTOOLS_EXPORT_H

#ifdef CSVTOOLS_BUILDING
#define CSVTOOLS_API __attribute__((visibility("default")))
#else
#define CSVTOOLS_API
#endif

#endif
