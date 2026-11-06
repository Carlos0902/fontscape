import AppKit
import CoreText
import Foundation
let file=CommandLine.arguments[1]
let provider=CGDataProvider(url:URL(fileURLWithPath:file) as CFURL)!
let graphics=CGFont(provider)!
let samples=["FontLab macOS Applications", "AVATAR To Wa VA Yo office affine ffi fi fl", "Hello, world! (123.45) [Test] — ‘quotes’", "Cafe\u{301} naïve façade Ångström", "系统设置 文件 编辑 窗口 帮助 0123456789", "Ǟǟ Ǡǡ Ǣǣ Ǩǩ Ǭǭ ǰ Ǵǵ Ȟȟ Ȧȧ Ȩȩ Ȯȯ", "ΆΈΉΊΌΎΏ άέήίόύώ ϊϋ ΐΰ", "xⁱ n⁵ 10⁶⁷⁸⁹ H₂O CO₃ a₀₁₂₃₄₅₆₇₈₉ ⁽x⁾ ₍y₎", "ϊ ΐ ṟ Ḹ ḹ ĺ ǰ ḻ ẗ Ḯ ḯ"]
var rows:[[String:Any]]=[]
for size:CGFloat in [11,13,17,24] {
 let font=CTFontCreateWithGraphicsFont(graphics,size,nil,nil)
 for text in samples {
  let line=CTLineCreateWithAttributedString(NSAttributedString(string:text,attributes:[NSAttributedString.Key(kCTFontAttributeName as String):font]))
  let runs=CTLineGetGlyphRuns(line) as! [CTRun]
  var missing=0;var finite=true;var overlaps=0
  for run in runs {
   let n=CTRunGetGlyphCount(run);var glyphs=[CGGlyph](repeating:0,count:n);var positions=[CGPoint](repeating:.zero,count:n)
   CTRunGetGlyphs(run,CFRange(location:0,length:0),&glyphs);CTRunGetPositions(run,CFRange(location:0,length:0),&positions)
   let actual=(CTRunGetAttributes(run) as NSDictionary)[kCTFontAttributeName] as! CTFont
   var boxes=[CGRect](repeating:.zero,count:n)
   CTFontGetBoundingRectsForGlyphs(actual,.horizontal,glyphs,&boxes,n)
   if n>1 { for i in 0..<(n-1) {
    if boxes[i].width>0 && boxes[i+1].width>0 && positions[i].x+boxes[i].maxX>positions[i+1].x+boxes[i+1].minX+0.01 { overlaps += 1 }
   } }
   missing += glyphs.filter{$0==0}.count;finite = finite && positions.allSatisfy{$0.x.isFinite && $0.y.isFinite}
  }
  rows.append(["size":size,"text":text,"advance":CTLineGetTypographicBounds(line,nil,nil,nil),"missingGlyphs":missing,"finitePositions":finite,"adjacentInkBoundsOverlaps":overlaps])
 }
}
FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject:rows,options:[.prettyPrinted,.sortedKeys]))
