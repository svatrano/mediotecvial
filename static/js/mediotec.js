document.addEventListener('DOMContentLoaded', function () {
    const faqQuestions = document.querySelectorAll('.faq-question');

    faqQuestions.forEach((question) => {
        question.addEventListener('click', function () {
            const faqItem = this.closest('.faq-item');
            const answer = faqItem.querySelector('.faq-answer');
            const expanded = this.getAttribute('aria-expanded') === 'true';

            this.setAttribute('aria-expanded', String(!expanded));
            faqItem.classList.toggle('open');

            if (!expanded) {
                answer.style.height = answer.scrollHeight + 'px';
            } else {
                answer.style.height = '0px';
            }
        });
    });

    window.addEventListener('resize', function () {
        document.querySelectorAll('.faq-item.open .faq-answer').forEach((answer) => {
            answer.style.height = answer.scrollHeight + 'px';
        });
    });
});
