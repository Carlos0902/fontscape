#import "FontHook.h"
#import <objc/runtime.h>

static NSString *replacement;
static BOOL installed = NO;
@interface NSFont (FontLab)
+ (NSFont *)fl_systemFontOfSize:(CGFloat)size;
+ (NSFont *)fl_boldSystemFontOfSize:(CGFloat)size;
+ (NSFont *)fl_systemFontOfSize:(CGFloat)size weight:(NSFontWeight)weight;
@end
@implementation NSFont (FontLab)
+ (NSFont *)fl_systemFontOfSize:(CGFloat)size {
    return [NSFont fontWithName:replacement size:size > 0 ? size : NSFont.systemFontSize] ?: [self fl_systemFontOfSize:size];
}
+ (NSFont *)fl_boldSystemFontOfSize:(CGFloat)size {
    return [NSFont fontWithName:replacement size:size > 0 ? size : NSFont.systemFontSize] ?: [self fl_boldSystemFontOfSize:size];
}
+ (NSFont *)fl_systemFontOfSize:(CGFloat)size weight:(NSFontWeight)weight {
    return [NSFont fontWithName:replacement size:size > 0 ? size : NSFont.systemFontSize] ?: [self fl_systemFontOfSize:size weight:weight];
}
@end
static void swap(SEL a, SEL b) {
    method_exchangeImplementations(class_getClassMethod(NSFont.class, a), class_getClassMethod(NSFont.class, b));
}
static void toggle(void) {
    swap(@selector(systemFontOfSize:), @selector(fl_systemFontOfSize:));
    swap(@selector(boldSystemFontOfSize:), @selector(fl_boldSystemFontOfSize:));
    swap(@selector(systemFontOfSize:weight:), @selector(fl_systemFontOfSize:weight:));
}
BOOL FLInstallHook(NSString *name) {
    NSCAssert(NSThread.isMainThread, @"Hook changes must run on the main thread");
    if (![NSFont fontWithName:name size:13]) return NO;
    replacement = [name copy];
    if (!installed) { toggle(); installed = YES; }
    return YES;
}
void FLRemoveHook(void) {
    NSCAssert(NSThread.isMainThread, @"Hook changes must run on the main thread");
    if (installed) { toggle(); installed = NO; replacement = nil; }
}
