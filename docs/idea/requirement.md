# Product requirement - idea

## Bối cảnh

Tôi muốn thảo luận về việc giải pháp dịch văn bản (có thể là xây dựng tool, cũng có thể là xây dựng một quy trình làm việc để đạt mục đích).

Tôi biết có nhiều tool dịch văn bản như DeepL.com hay vài tool khác sử dụng AI, có thể dịch các file văn bản word, excel, powerpoint, "cố gắng" giữ nguyên định dạng cũ. Bản thân tôi cũng có vài lần sử dụng DeepL (acocunt trả tiền), ngoài ra cũng thử dụng thử dịch vụ khác nhưng ở thời điểm đó, cảm thấy chất lượng dịch chưa tốt.
Tài liệu tôi cần dịch chủ yếu là tài liệu mang tính kỹ thuật hoặc business, không phải văn chương, cần độ chính xác và phù hợp về thuật ngữ chuyên môn. Có thể một số tool dịch tự động (AI) giờ tốt hơn nhiều nhưng tôi chưa thử.
Dạo này tôi dùng Gemini Pro để dịch văn bản (tài liệu hơn 100 trang). Tôi phải cắt văn bản nhỏ ra làm vài phần, dùng Genini Web để dịch văn bản đó, sau đó dùng tay để copy/paste lại định dạng cũ. Tất nhiên là tốn thời gian, công sức

Tôi cũng sẵn sàng sử dụng các tool trả phí, nhưng với điều kiện nó phải thỏa mãn được yêu cầu của tôi và mức chi phí hợp lý.

## Yêu cầu của tôi

1. Đối tượng: tài liệu kỹ thuật IT, giới thiệu sản phẩm (ví dụ khoáng vi lượng), proposal dự án IT... Nói chung là tài liệu có tính chuyên môn, không có tính văn chương, yêu cầu sự chính xác về mặt thuật ngữ (có thể có thuật ngữ riêng thuộc về khách hàng, dự án).
2. Chất lượng dịch tốt..
3. Cố gắng giữ được định dạng văn bản gốc.
4. Tốn ít thời gian (giảm thời gian con người làm việc).
5. Tài liệu có thể được dịch đi dịch lại nhiều lần (do phải điều chỉnh thuật ngữ, thêm yêu cầu bổ sung, update lại tài liệu gốc), cần phải kế thừa được từ các lần dịch trước, không phải là mỗi lần lại dịch từ đầu (tôi nghĩ các dịch vụ dịch thuật online chưa làm được việc này??)
7. Tôi không cần có một general translation tool, chỉ cần một tool phục vụ tốt lĩnh vực mình cần, thỏa mãn các yêu cầu của mình.
8. Nếu tự xây dựng tool, ban đầu có thể là command line (CLI) để test tính năng (PoC) và thực hiện nhu cầu công việc trước, nhưng về lâu dài thì cũng muốn đóng gói thành chương trình có GUI, chạy được trên cả Windows/Mac/Ubuntu (hoặc là giao diện Web).

## Một vài suy nghĩ của tôi

Đây là các suy nghĩ, ý tưởng của tôi. Có thể có nhiều chỗ không đúng, do tôi không cập nhật về khả năng của các tool dịch hiện nay.
1. Sử dụng các dịch vụ sẽ tốn nhiều chi phí khi cần thường xuyên update bản dịch gốc, update yêu cầu đối với việc dịch (ví dụ bổ sung thuật ngữ).
2. Với kinh nghiệm của một lập trình viên, tôi có thể tự xây dựng một tool để có thể đáp ứng được nhiều yêu cầu của mình một cách linh động.
3. Về mặt chi phí, sau này khi hệ thống hoạt động tốt, tôi có thể gắn API của các AI vào (trả phí cho nó), nhưng ở giai đoạn đầu (PoC), có thể áp dụng các biện pháp tương đối thô sơ, đơn giản hơn như là: Yêu cầu Cursor IDE dịch tài liệu, thay vì dùng AI API.
4. Để có thể lặp lại việc dịch thuật nhiều lần, tôi thiên về xu hướng: Lưu lại từ điển dịch (với input là mỗi đoạn văn, hoặc một object (text box, list item)) trong văn bản, và kết quả dịch của nó. Khi cần update lại văn bản dịch, nếu nguyên một văn bản chưa tồn tại, hệ thống sẽ giữ nguyên kết quả dịch các đoạn có sẵn, và chỉ update các văn bản mới/có thay đổi.
5. Chú ý rằng trọng tâm của tôi là xây dựng một giải pháp, quy trình hợp lý cho mục đích này (cân bằng giữa yêu cầu và chi phí), không nhất thiết phải là tự mình xây dựng tool.

Ngoài ra, một chút kinh nghiệm khác của tôi:
* Việc cập nhật, thay đổi nội dung vào file Word, Excel, PowerPoint với cấu trúc phức tạp (ví dụ có nhiều chart, object, định dạng) tương đối phức tạp, các thư viện của các ngôn ngữ lập trình gần như không làm được hoàn hảo. Sử dụng Excel COM chạy trên máy Windows để edit nội dung file MS Office (thông qua chương trình viết bằng PowerShell) là giải pháp toàn diện nhất để có chương trình edit file MS Office không gây ra vỡ định dạng.

## Yêu cầu cho bạn (AI)

Ỹ đọc nội dung trên và đưa ra các ý kiến, đề xuất của bạn.
Không nhất thiết phải đi theo suy nghĩ của tôi. Chúng ta sẽ tìm ra các giải pháp phù hợp cho công việc, cũng như phù hợp với thời gian phát triển (ví dụ, ban đầu tôi chỉ cần dịch file Excel, việc này tôi nghĩ tương đối dễ, có thể hoàn toàn áp dụng ý tưởng ở trên cũng phù hợp). Sau đó là áp dụng với file Word, sẽ phức tạp hơn. Cuối cùng là áp dụng với PowerPoint.